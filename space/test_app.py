import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi import HTTPException, UploadFile
from requests import ConnectionError, Response
from starlette.datastructures import Headers
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).parent))
import app  # noqa: E402


class FilenameDetectionTests(unittest.TestCase):
    def test_normal_names_do_not_trigger_rename(self):
        self.assertFalse(app.is_garbled_filename("季度报告.pdf"))
        self.assertFalse(app.is_garbled_filename("product-roadmap-v2.pptx"))

    def test_mojibake_and_url_encoded_names_trigger_rename(self):
        self.assertTrue(app.is_garbled_filename("æµ‹è¯•æŠ¥å‘Š.pdf"))
        self.assertTrue(app.is_garbled_filename("%E6%B5%8B%E8%AF%95%E6%8A%A5%E5%91%8A.pdf"))
        self.assertTrue(app.is_garbled_filename("���?.pdf"))

    def test_encoding_candidates_recover_chinese(self):
        candidates = app.filename_repair_candidates("æµ‹è¯•æŠ¥å‘Š.pdf")
        self.assertIn("测试报告.pdf", candidates)

    def test_generated_name_is_sanitized_and_keeps_extension(self):
        sanitized = app.sanitized_display_filename("../测试报告.exe", "���.pdf")
        self.assertEqual(sanitized, "测试报告.pdf")

    def test_generated_name_without_extension_removes_path_markers(self):
        sanitized = app.sanitized_display_filename("../测试报告", "���")
        self.assertEqual(sanitized, "测试报告")

    def test_safe_upload_name_removes_client_paths(self):
        self.assertEqual(app.safe_upload_name(r"C:\Users\test\报告.pdf"), "报告.pdf")


class SmartFilenameTests(unittest.IsolatedAsyncioTestCase):
    async def test_glm_renames_garbled_and_normal_filenames(self):
        responses = [
            json.dumps({"filename": "测试报告.pdf"}, ensure_ascii=False),
            json.dumps({"filename": "季度工作报告.pdf"}, ensure_ascii=False),
        ]
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "SMART_FILENAME_MODEL", "glm-5.2"),
            patch.object(app, "call_glm_filename_rename", side_effect=responses) as rename,
        ):
            filename, model = await app.smart_display_filename("æµ‹è¯•æŠ¥å‘Š.pdf", "application/pdf")
            normal_filename, normal_model = await app.smart_display_filename("季度报告.pdf", "application/pdf")

        self.assertEqual(filename, "测试报告.pdf")
        self.assertEqual(model, "glm-5.2")
        self.assertEqual(normal_filename, "季度工作报告.pdf")
        self.assertEqual(normal_model, "glm-5.2")
        self.assertEqual(rename.call_count, 2)

    async def test_model_failure_falls_back_to_encoding_repair(self):
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "call_glm_filename_rename", side_effect=RuntimeError("offline")),
        ):
            filename, model = await app.smart_display_filename("æµ‹è¯•æŠ¥å‘Š.pdf", "application/pdf")

        self.assertEqual(filename, "测试报告.pdf")
        self.assertEqual(model, "encoding-repair")

    async def test_model_failure_uses_type_normalized_filename(self):
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "call_glm_filename_rename", side_effect=RuntimeError("offline")),
        ):
            filename, model = await app.smart_display_filename("季度报告.pdf", "application/pdf")

        self.assertEqual(filename, "季度报告 · PDF.pdf")
        self.assertEqual(model, "type-normalization")

    def test_filename_request_includes_image_evidence(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": '{"filename":"香港列表.png"}'}}]}
        ).encode("utf-8")
        evidence = {"ocrText": "Hong Kong 01", "caption": "香港条目列表"}

        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app.urllib.request, "urlopen", return_value=response) as urlopen,
        ):
            result = app.call_glm_filename_rename("Screenshot.png", "image/png", [], evidence)

        request = urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode("utf-8"))
        user_payload = json.loads(request_payload["messages"][1]["content"])
        self.assertEqual(user_payload["imageAnalysis"], evidence)
        self.assertEqual(result, '{"filename":"香港列表.png"}')

    async def test_unchanged_model_response_uses_objective_type(self):
        response = json.dumps({"filename": "季度报告.pdf"}, ensure_ascii=False)
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "call_glm_filename_rename", return_value=response),
        ):
            filename, model = await app.smart_display_filename("季度报告.pdf", "application/pdf")

        self.assertEqual(filename, "季度报告 · PDF.pdf")
        self.assertEqual(model, "type-normalization")


class ImageAnalysisTests(unittest.IsolatedAsyncioTestCase):
    def test_small_png_keeps_source_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "small.png"
            app.Image.new("RGB", (120, 80), "white").save(path, format="PNG")
            prepared = app.prepared_image_payload(path, "image/png")

        self.assertIsNotNone(prepared)
        payload, mime_type = prepared
        self.assertEqual(mime_type, "image/png")
        self.assertTrue(payload.startswith(b"\x89PNG"))

    def test_large_image_is_resized_and_encoded_as_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.png"
            app.Image.new("RGB", (2400, 1800), "white").save(path, format="PNG")
            prepared = app.prepared_image_payload(path, "image/png")

        self.assertIsNotNone(prepared)
        payload, mime_type = prepared
        self.assertEqual(mime_type, "image/jpeg")
        self.assertTrue(payload.startswith(b"\xff\xd8"))

    def test_unsupported_image_mime_is_skipped(self):
        self.assertIsNone(app.prepared_image_payload(Path("unused.svg"), "image/svg+xml"))

    async def test_image_analysis_returns_bounded_ocr_and_caption(self):
        response = {"ocrText": "Hong Kong 01\nHong Kong 02", "caption": "531x441 图片，视觉类别可能包括 web site（47%）。"}
        with (
            patch.object(app, "prepared_image_payload", return_value=(b"image", "image/png")),
            patch.object(app, "call_image_analysis", return_value=response),
        ):
            result = await app.analyze_image(Path("test.png"), "image/png")

        self.assertEqual(result, response)

    async def test_image_analysis_failure_is_non_fatal(self):
        with (
            patch.object(app, "prepared_image_payload", side_effect=OSError("decode failed")),
        ):
            result = await app.analyze_image(Path("test.png"), "image/png")

        self.assertIsNone(result)

    def test_caption_combines_dimensions_labels_and_ocr_presence(self):
        image = BytesIO()
        app.Image.new("RGB", (531, 441), "white").save(image, format="PNG")
        with (
            patch.object(app, "extract_image_ocr", return_value="Hong Kong 01"),
            patch.object(app, "classify_image", return_value=[("web site", 0.4743), ("menu", 0.0455)]),
        ):
            result = app.call_image_analysis(image.getvalue())

        self.assertEqual(result["ocrText"], "Hong Kong 01")
        self.assertEqual(result["caption"], "531x441 图片，视觉类别可能包括 web site（47%）、menu（5%），包含可识别文字。")

class HuggingFaceRetryTests(unittest.TestCase):
    def test_retryable_network_error_is_retried(self):
        operation = Mock(side_effect=[ConnectionError("offline"), "ok"])
        with patch.object(app.time, "sleep") as sleep:
            result = app.run_hf_with_retry(operation, "test operation")

        self.assertEqual(result, "ok")
        self.assertEqual(operation.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_final_network_error_becomes_service_unavailable(self):
        with (
            patch.object(app.hf_api, "upload_file", side_effect=ConnectionError("offline")),
            patch.object(app.time, "sleep"),
            self.assertRaises(HTTPException) as raised,
        ):
            app.upload_dataset_file("files/test.txt", BytesIO(b"test"), "Upload test")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "存储服务暂时不可用，请稍后重试")

    def test_auth_error_is_not_retried(self):
        response = Response()
        response.status_code = 401
        error = app.HfHubHTTPError("unauthorized", response=response)
        operation = Mock(side_effect=error)
        with (
            patch.object(app.time, "sleep") as sleep,
            self.assertRaises(app.HfHubHTTPError),
        ):
            app.run_hf_with_retry(operation, "test operation")

        operation.assert_called_once()
        sleep.assert_not_called()

    def test_in_memory_payload_is_rewound_before_retry(self):
        positions = []

        def upload_file(**kwargs):
            source = kwargs["path_or_fileobj"]
            positions.append(source.tell())
            if len(positions) == 1:
                source.read()
                raise ConnectionError("offline")

        with (
            patch.object(app.hf_api, "upload_file", side_effect=upload_file),
            patch.object(app.time, "sleep"),
        ):
            app.upload_dataset_file("index.json", BytesIO(b"[]"), "Update index")

        self.assertEqual(positions, [0, 0])

class AssetCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_created_asset_keeps_original_and_smart_display_names(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/assets",
                "headers": [],
                "client": ("203.0.113.9", 1234),
            }
        )
        upload = UploadFile(
            file=BytesIO(b"smart filename rename test"),
            filename="Quarterly_Report_FINAL_v3.txt",
            headers=Headers({"content-type": "text/plain"}),
        )

        image_evidence = {"ocrText": "Hong Kong 01", "caption": "香港条目列表"}
        analyze_image = AsyncMock(return_value=image_evidence)
        smart_filename = AsyncMock(return_value=("季度报告 v3.txt", "glm-5.2"))

        with (
            patch.object(app, "ensure_dataset"),
            patch.object(app.hf_api, "upload_file") as upload_file,
            patch.object(app, "analyze_image", new=analyze_image),
            patch.object(app, "smart_display_filename", new=smart_filename),
            patch.object(app, "load_index", return_value=[]),
            patch.object(app, "save_index") as save_index,
        ):
            result = await app.create_asset(request, upload, "", "upload-demo")

        self.assertEqual(result["originalName"], "Quarterly_Report_FINAL_v3.txt")
        self.assertEqual(result["displayName"], "季度报告 v3.txt")
        self.assertEqual(result["renameModel"], "glm-5.2")
        upload_file.assert_called_once()
        save_index.assert_called_once()
        self.assertEqual(save_index.call_args.args[0][0]["displayName"], "季度报告 v3.txt")
        analyze_image.assert_awaited_once()
        smart_filename.assert_awaited_once_with("Quarterly_Report_FINAL_v3.txt", "text/plain", image_evidence)


class AssetDownloadTests(unittest.TestCase):
    def test_download_uses_original_name_without_modifying_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "stored-id.txt"
            original_bytes = b"original file bytes\x00\xff"
            source.write_bytes(original_bytes)
            item = {
                "id": "stored-id",
                "originalName": "Quarterly_Report_FINAL_v3.txt",
                "displayName": "季度报告 v3.txt",
                "mimeType": "text/plain",
            }

            with patch.object(app, "file_item", return_value=(item, source)):
                response = app.download_file("stored-id", "read-demo")

            self.assertEqual(Path(response.path), source)
            self.assertEqual(source.read_bytes(), original_bytes)
            self.assertIn("attachment", response.headers["content-disposition"])
            self.assertIn("Quarterly_Report_FINAL_v3.txt", response.headers["content-disposition"])
            self.assertNotIn("%E5%AD%A3%E5%BA%A6%E6%8A%A5%E5%91%8A", response.headers["content-disposition"])

    def test_download_uses_original_name_for_legacy_asset(self):
        item = {
            "id": "legacy-id",
            "originalName": "legacy-report.pdf",
            "mimeType": "application/pdf",
        }
        with patch.object(app, "file_item", return_value=(item, Path("legacy-id.pdf"))):
            response = app.download_file("legacy-id", "read-demo")

        self.assertIn('filename="legacy-report.pdf"', response.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
