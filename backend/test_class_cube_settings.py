import json
import tempfile
import unittest
from pathlib import Path

from app.class_cube_settings import (
    ClassCubeSettingsError,
    save_class_cube_settings,
    validate_wecom_webhook,
)
from app.service import save_settings_to_disk
from unittest.mock import patch


class ClassCubeSettingsTest(unittest.TestCase):
    def test_save_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                '{"webhook_url":"xxqd","auto_enabled":true}',
                encoding="utf-8",
            )
            save_class_cube_settings(
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
                path,
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["webhook_url"], "xxqd")
            self.assertTrue(saved["auto_enabled"])
            self.assertTrue(
                saved["class_cube_webhook_url"].endswith("key=abc")
            )

    def test_rejects_non_wecom_webhook(self):
        with self.assertRaises(ClassCubeSettingsError):
            validate_wecom_webhook("https://example.com/hook")

    def test_xxqd_save_preserves_class_cube_webhook(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                '{"class_cube_webhook_url":"wecom"}',
                encoding="utf-8",
            )
            with patch("app.service.SETTINGS_FILE", path), patch(
                "app.service.ensure_dirs"
            ):
                save_settings_to_disk(True, ["08:00:00"], "xxqd")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["class_cube_webhook_url"], "wecom"
            )
