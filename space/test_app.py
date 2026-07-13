import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import UploadFile
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
    async def test_glm_renames_only_garbled_filename(self):
        response = json.dumps({"filename": "测试报告.pdf"}, ensure_ascii=False)
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "SMART_FILENAME_MODEL", "glm-5.2"),
            patch.object(app, "call_glm_filename_rename", return_value=response) as rename,
        ):
            filename, model = await app.smart_display_filename("æµ‹è¯•æŠ¥å‘Š.pdf", "application/pdf")
            normal_filename, normal_model = await app.smart_display_filename("季度报告.pdf", "application/pdf")

        self.assertEqual(filename, "测试报告.pdf")
        self.assertEqual(model, "glm-5.2")
        self.assertEqual(normal_filename, "季度报告.pdf")
        self.assertIsNone(normal_model)
        rename.assert_called_once()

    async def test_model_failure_falls_back_to_encoding_repair(self):
        with (
            patch.object(app, "SMART_FILENAME_BASE_URL", "https://example.test/v1"),
            patch.object(app, "SMART_FILENAME_API_KEY", "test-key"),
            patch.object(app, "call_glm_filename_rename", side_effect=RuntimeError("offline")),
        ):
            filename, model = await app.smart_display_filename("æµ‹è¯•æŠ¥å‘Š.pdf", "application/pdf")

        self.assertEqual(filename, "测试报告.pdf")
        self.assertEqual(model, "encoding-repair")


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
            filename="æµ‹è¯•æŠ¥å‘Š.txt",
            headers=Headers({"content-type": "text/plain"}),
        )

        with (
            patch.object(app, "ensure_dataset"),
            patch.object(app.hf_api, "upload_file") as upload_file,
            patch.object(
                app,
                "smart_display_filename",
                new=AsyncMock(return_value=("测试报告.txt", "glm-5.2")),
            ),
            patch.object(app, "load_index", return_value=[]),
            patch.object(app, "save_index") as save_index,
        ):
            result = await app.create_asset(request, upload, "", "upload-demo")

        self.assertEqual(result["originalName"], "æµ‹è¯•æŠ¥å‘Š.txt")
        self.assertEqual(result["displayName"], "测试报告.txt")
        self.assertEqual(result["renameModel"], "glm-5.2")
        upload_file.assert_called_once()
        save_index.assert_called_once()
        self.assertEqual(save_index.call_args.args[0][0]["displayName"], "测试报告.txt")


if __name__ == "__main__":
    unittest.main()
