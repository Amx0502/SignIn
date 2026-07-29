import json
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import SETTINGS_FILE


class ClassCubeSettingsError(ValueError):
    pass


def validate_wecom_webhook(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    valid = (
        parsed.scheme == "https"
        and parsed.hostname == "qyapi.weixin.qq.com"
        and parsed.path == "/cgi-bin/webhook/send"
        and bool(parse_qs(parsed.query).get("key"))
    )
    if not valid:
        raise ClassCubeSettingsError("企业微信机器人地址无效")
    return value


def load_class_cube_settings(path: Path = SETTINGS_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ClassCubeSettingsError("settings.json 读取失败") from exc
    if not isinstance(data, dict):
        raise ClassCubeSettingsError("settings.json 必须是对象格式")
    value = str(data.get("class_cube_webhook_url", "")).strip()
    return {
        "class_cube_webhook_url": value,
        "webhook_configured": bool(value),
    }


def save_class_cube_settings(
    webhook_url: str,
    path: Path = SETTINGS_FILE,
) -> dict:
    value = validate_wecom_webhook(webhook_url)
    try:
        data = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists()
            else {}
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ClassCubeSettingsError("settings.json 读取失败") from exc
    if not isinstance(data, dict):
        raise ClassCubeSettingsError("settings.json 必须是对象格式")
    data["class_cube_webhook_url"] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return {
        "class_cube_webhook_url": value,
        "webhook_configured": bool(value),
    }

