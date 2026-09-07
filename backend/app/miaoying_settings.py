import json
import os
import tempfile
from pathlib import Path

from .class_cube_settings import validate_wecom_webhook
from .config import SETTINGS_FILE


class MiaoyingSettingsError(ValueError):
    pass


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise MiaoyingSettingsError("settings.json 读取失败") from exc
    if not isinstance(data, dict):
        raise MiaoyingSettingsError("settings.json 必须是对象格式")
    return data


def load_miaoying_settings(path: Path = SETTINGS_FILE) -> dict:
    value = str(_read(path).get("miaoying_webhook_url", "")).strip()
    return {
        "miaoying_webhook_url": value,
        "webhook_configured": bool(value),
    }


def save_miaoying_settings(webhook_url: str, path: Path = SETTINGS_FILE) -> dict:
    try:
        value = validate_wecom_webhook(webhook_url)
    except ValueError as exc:
        raise MiaoyingSettingsError(str(exc)) from exc
    data = _read(path)
    data["miaoying_webhook_url"] = value
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
        "miaoying_webhook_url": value,
        "webhook_configured": bool(value),
    }
