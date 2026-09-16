import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .config import SETTINGS_FILE


DEFAULT_PURCHASE_URL = "https://m.tb.cn/h.8sGQxfh?tk=Dz6vT8OEx7h"
SETTINGS_KEY = "site_settings"
MAX_URL_LENGTH = 2048


class SiteSettingsError(ValueError):
    pass


def normalize_purchase_url(value: str | None) -> str:
    url = str(value or "").strip()
    if not url:
        raise SiteSettingsError("购买链接不能为空")
    if len(url) > MAX_URL_LENGTH:
        raise SiteSettingsError("购买链接过长")
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise SiteSettingsError("购买链接格式无效") from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or port is not None and not 1 <= port <= 65535
    ):
        raise SiteSettingsError("购买链接必须是有效的 http 或 https 地址")
    return url


def _read_settings(path: Path) -> dict:
    try:
        data = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists()
            else {}
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteSettingsError("settings.json 读取失败") from exc
    if not isinstance(data, dict):
        raise SiteSettingsError("settings.json 必须是对象格式")
    return data


def load_site_settings(path: Path = SETTINGS_FILE) -> dict:
    data = _read_settings(path)
    raw = data.get(SETTINGS_KEY)
    value = raw.get("purchase_url") if isinstance(raw, dict) else None
    if value is None:
        value = DEFAULT_PURCHASE_URL
    return {"purchase_url": normalize_purchase_url(value)}


def save_purchase_url(
    value: str,
    path: Path = SETTINGS_FILE,
) -> dict:
    purchase_url = normalize_purchase_url(value)
    data = _read_settings(path)
    data[SETTINGS_KEY] = {"purchase_url": purchase_url}
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return {"purchase_url": purchase_url}
