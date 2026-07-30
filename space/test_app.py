import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi import BackgroundTasks, HTTPException, UploadFile
from fastapi.testclient import TestClient
from requests import ConnectionError, Response
from starlette.datastructures import Headers, MutableHeaders
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

    async def test_filename_uses_metadata_only_upstream_when_local_key_is_unavailable(self):
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", ""),
            patch.object(app, "SMART_FILENAME_API_KEY", ""),
            patch.object(app, "SMART_FILENAME_UPSTREAM_URL", "https://example.test/internal/smart-filename"),
            patch.object(app, "INTERNAL_API_KEY", "internal-key"),
            patch.object(
                app,
                "call_upstream_filename_rename",
                return_value=("香港数据列表截图.png", "glm-5.2"),
            ) as upstream,
        ):
            filename, model = await app.smart_display_filename(
                "Screenshot.png",
                "image/png",
                {"ocrText": "Hong Kong", "caption": "列表截图"},
            )

        self.assertEqual(filename, "香港数据列表截图.png")
        self.assertEqual(model, "glm-5.2")
        upstream.assert_called_once_with(
            "Screenshot.png",
            "image/png",
            {"ocrText": "Hong Kong", "caption": "列表截图"},
        )


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


class LocalStorageTests(unittest.TestCase):
    def test_local_storage_writes_and_reads_files_and_index_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            source = storage / "source.txt"
            source.write_bytes(b"local-file")
            with (
                patch.object(app, "STORAGE_BACKEND", "local"),
                patch.object(app, "LOCAL_STORAGE_DIR", storage),
                patch.object(app, "LOCAL_STORAGE_MIN_FREE_BYTES", 0),
                patch.object(app, "LOCAL_STORAGE_MAX_BYTES", 0),
            ):
                app.upload_storage_file("files/stored.txt", source, "Upload")
                app.save_index([{"id": "stored", "filename": "stored.txt"}])
                items = app.load_index()

            self.assertEqual((storage / "files" / "stored.txt").read_bytes(), b"local-file")
            self.assertEqual(items, [{"id": "stored", "filename": "stored.txt"}])
            self.assertEqual(list(storage.rglob("*.tmp")), [])

    def test_local_storage_rejects_parent_path_escape(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(app, "LOCAL_STORAGE_DIR", Path(directory)),
            self.assertRaises(HTTPException) as raised,
        ):
            app.safe_storage_path("../outside.txt")

        self.assertEqual(raised.exception.status_code, 500)

    def test_local_storage_enforces_configured_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            files = storage / "files"
            files.mkdir()
            (files / "existing.bin").write_bytes(b"12345")
            with (
                patch.object(app, "LOCAL_STORAGE_DIR", storage),
                patch.object(app, "LOCAL_STORAGE_MIN_FREE_BYTES", 0),
                patch.object(app, "LOCAL_STORAGE_MAX_BYTES", 6),
                self.assertRaises(HTTPException) as raised,
            ):
                app.ensure_local_storage(required_bytes=2)

        self.assertEqual(raised.exception.status_code, 507)
        self.assertEqual(raised.exception.detail, "本地存储已达到容量上限")

    def test_local_file_lookup_uses_migrated_dataset_path(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            file_path = storage / "files" / "stored-id.txt"
            file_path.parent.mkdir()
            file_path.write_bytes(b"migrated")
            item = {
                "id": "stored-id",
                "filename": "stored-id.txt",
                "path": "files/stored-id.txt",
                "originalName": "report.txt",
                "mimeType": "text/plain",
            }
            with (
                patch.object(app, "STORAGE_BACKEND", "local"),
                patch.object(app, "LOCAL_STORAGE_DIR", storage),
                patch.object(app, "LOCAL_STORAGE_MIN_FREE_BYTES", 0),
                patch.object(app, "LOCAL_STORAGE_MAX_BYTES", 0),
                patch.object(app, "session_for", return_value={"role": "download", "name": "Reader"}),
                patch.object(app, "load_index", return_value=[item]),
            ):
                loaded_item, loaded_path = app.file_item("stored-id", "read-demo")

        self.assertEqual(loaded_item, item)
        self.assertEqual(loaded_path, file_path.resolve())


class UpstreamAuthorizationTests(unittest.TestCase):
    def setUp(self):
        app.auth_cache.clear()

    def tearDown(self):
        app.auth_cache.clear()

    def test_valid_invite_is_cached_without_storing_plaintext_key(self):
        response = Mock(status_code=200)
        response.json.return_value = {"role": "upload", "name": "upstream"}
        with (
            patch.object(app, "INVITES", {}),
            patch.object(app, "AUTH_UPSTREAM_URL", "https://auth.example.test"),
            patch.object(app, "AUTH_CACHE_TTL_SECONDS", 600),
            patch.object(app.requests, "post", return_value=response) as post,
        ):
            first = app.session_for("private-upload-invite")
            second = app.session_for("private-upload-invite")

        self.assertEqual(first["role"], "upload")
        self.assertEqual(second, first)
        post.assert_called_once()
        self.assertNotIn("private-upload-invite", app.auth_cache)
        self.assertIn(app.auth_cache_key("private-upload-invite"), app.auth_cache)

    def test_invalid_upstream_invite_remains_unauthorized(self):
        response = Mock(status_code=401)
        with (
            patch.object(app, "INVITES", {}),
            patch.object(app, "AUTH_UPSTREAM_URL", "https://auth.example.test"),
            patch.object(app.requests, "post", return_value=response),
            self.assertRaises(HTTPException) as raised,
        ):
            app.session_for("invalid")

        self.assertEqual(raised.exception.status_code, 401)

    def test_recent_cached_authorization_survives_upstream_outage(self):
        key = app.auth_cache_key("cached-invite")
        app.auth_cache[key] = (app.time.monotonic(), {"role": "download", "name": "Office"})
        with (
            patch.object(app, "INVITES", {}),
            patch.object(app, "AUTH_UPSTREAM_URL", "https://auth.example.test"),
            patch.object(app, "AUTH_CACHE_TTL_SECONDS", 0),
            patch.object(app, "AUTH_CACHE_STALE_SECONDS", 86400),
            patch.object(app.requests, "post", side_effect=ConnectionError("offline")),
        ):
            session = app.session_for("cached-invite")

        self.assertEqual(session, {"role": "download", "name": "Office"})


class CompatibilityProxyTests(unittest.TestCase):
    def test_only_public_storage_routes_can_be_proxied(self):
        self.assertEqual(app.compatibility_path("api/session"), "/api/session")
        self.assertEqual(app.compatibility_path("/api/assets/item-1"), "/api/assets/item-1")
        self.assertEqual(app.compatibility_path("files/item-1/download"), "/files/item-1/download")

        for path in ("", "internal/smart-filename", "docs", "api/assets/item-1/extra"):
            with self.subTest(path=path), self.assertRaises(HTTPException) as raised:
                app.compatibility_path(path)
            self.assertEqual(raised.exception.status_code, 404)

    def test_proxy_headers_keep_required_metadata_without_forwarding_host(self):
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/compat/api/assets",
            "headers": [],
            "client": ("203.0.113.9", 1234),
        }
        request = Request(scope)
        headers = MutableHeaders(scope=request.scope)
        headers["host"] = "proxy.example.test"
        headers["content-type"] = "multipart/form-data; boundary=test"
        headers["content-length"] = "123"
        headers["x-invite-code"] = "private"
        headers["x-forwarded-for"] = "198.51.100.8"
        headers["connection"] = "keep-alive"

        forwarded = app.compatibility_request_headers(request)

        self.assertNotIn("host", forwarded)
        self.assertNotIn("connection", forwarded)
        self.assertEqual(forwarded["content-length"], "123")
        self.assertEqual(forwarded["x-invite-code"], "private")
        self.assertEqual(forwarded["x-forwarded-for"], "198.51.100.8")
        self.assertEqual(forwarded["accept-encoding"], "identity")

    def test_proxy_response_headers_preserve_download_metadata(self):
        response = app.httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'attachment; filename="report.pdf"',
                "content-length": "42",
                "server": "upstream",
                "connection": "close",
            },
        )

        forwarded = app.compatibility_response_headers(response)

        self.assertEqual(forwarded["content-type"], "application/pdf")
        self.assertEqual(forwarded["content-length"], "42")
        self.assertIn("report.pdf", forwarded["content-disposition"])
        self.assertNotIn("server", forwarded)
        self.assertNotIn("connection", forwarded)

    def test_proxy_streams_query_body_and_invite_header_to_upstream(self):
        captured: dict[str, object] = {}
        original_async_client = app.httpx.AsyncClient

        class ProxyResponseStream(app.httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"ok":"true"}'

        async def upstream(request: app.httpx.Request) -> app.httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["invite"] = request.headers.get("x-invite-code")
            captured["body"] = await request.aread()
            return app.httpx.Response(
                200,
                headers={"content-type": "application/json"},
                stream=ProxyResponseStream(),
            )

        def proxy_client(**_kwargs):
            return original_async_client(transport=app.httpx.MockTransport(upstream))

        with (
            patch.object(app, "COMPAT_UPSTREAM_URL", "https://storage.example.test"),
            patch.object(app.httpx, "AsyncClient", side_effect=proxy_client),
            TestClient(app.app) as client,
        ):
            response = client.post(
                "/compat/api/session?source=intranet",
                headers={"X-Invite-Code": "private"},
                json={"invite": "private"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": "true"})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(
            captured["url"],
            "https://storage.example.test/api/session?source=intranet",
        )
        self.assertEqual(captured["invite"], "private")
        self.assertEqual(json.loads(captured["body"]), {"invite": "private"})


class AssetCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_created_asset_returns_before_background_image_analysis(self):
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
            file=BytesIO(b"fake image bytes"),
            filename="Screenshot.png",
            headers=Headers({"content-type": "image/png"}),
        )
        background_tasks = BackgroundTasks()

        image_evidence = {"ocrText": "Hong Kong 01", "caption": "香港条目列表"}
        analyze_image = AsyncMock(return_value=image_evidence)
        smart_filename = AsyncMock(
            side_effect=[
                ("截图 · 图片.png", "type-normalization"),
                ("香港数据列表截图.png", "glm-5.2"),
            ]
        )

        with (
            patch.object(app, "ensure_dataset"),
            patch.object(app.hf_api, "upload_file") as upload_file,
            patch.object(app, "analyze_image", new=analyze_image),
            patch.object(app, "smart_display_filename", new=smart_filename),
            patch.object(app, "load_index", return_value=[]),
            patch.object(app, "save_index") as save_index,
            patch.object(app, "update_asset_display_name", return_value=True) as update_display_name,
        ):
            result = await app.create_asset(request, background_tasks, upload, "", "upload-demo")

            self.assertEqual(result["originalName"], "Screenshot.png")
            self.assertEqual(result["displayName"], "截图 · 图片.png")
            self.assertEqual(result["renameModel"], "type-normalization")
            upload_file.assert_called_once()
            save_index.assert_called_once()
            self.assertEqual(save_index.call_args.args[0][0]["displayName"], "截图 · 图片.png")
            analyze_image.assert_not_awaited()
            smart_filename.assert_awaited_once_with("Screenshot.png", "image/png")
            self.assertEqual(len(background_tasks.tasks), 1)

            await background_tasks()

        analyze_image.assert_awaited_once()
        self.assertEqual(smart_filename.await_count, 2)
        smart_filename.assert_awaited_with("Screenshot.png", "image/png", image_evidence)
        update_display_name.assert_called_once_with(
            result["id"],
            "香港数据列表截图.png",
            "glm-5.2",
            "截图 · 图片.png",
        )

    def test_background_display_name_update_does_not_overwrite_a_newer_name(self):
        item = {
            "id": "stored-id",
            "originalName": "Screenshot.png",
            "displayName": "用户更新后的名称.png",
        }
        with (
            patch.object(app, "load_index", return_value=[item]),
            patch.object(app, "save_index") as save_index,
        ):
            updated = app.update_asset_display_name(
                "stored-id",
                "后台视觉名称.png",
                "glm-5.2",
                "截图 · 图片.png",
            )

        self.assertFalse(updated)
        save_index.assert_not_called()


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
