import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from .config import SETTINGS_FILE


class ClassCubeSettingsError(ValueError):
    pass


_WECOM_WEBHOOK_HOST = "qyapi.weixin.qq.com"
_WECOM_WEBHOOK_PATH = "/cgi-bin/webhook/send"
_WECOM_WEBHOOK_KEY = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def validate_wecom_webhook(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
        port = parsed.port
    except ValueError as exc:
        raise ClassCubeSettingsError("企业微信机器人地址无效") from exc
    if not (
        parsed.scheme.lower() == "https"
        and parsed.hostname == _WECOM_WEBHOOK_HOST
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and parsed.path == _WECOM_WEBHOOK_PATH
        and not parsed.params
        and not parsed.fragment
        and len(query) == 1
        and query[0][0] == "key"
        and _WECOM_WEBHOOK_KEY.fullmatch(query[0][1])
    ):
        raise ClassCubeSettingsError("企业微信机器人地址无效")
    return (
        f"https://{_WECOM_WEBHOOK_HOST}{_WECOM_WEBHOOK_PATH}?"
        f"{urlencode(query)}"
    )


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

