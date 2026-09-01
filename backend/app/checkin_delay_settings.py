import json
import os
import tempfile
from pathlib import Path

from .config import SETTINGS_FILE


DEFAULT_MIN_SECONDS = 1
DEFAULT_MAX_SECONDS = 18
MAX_DELAY_SECONDS = 300
SETTINGS_KEY = "checkin_delay_settings"


class CheckinDelaySettingsError(ValueError):
    pass


def _integer(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise CheckinDelaySettingsError(f"{field_name}必须是整数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise CheckinDelaySettingsError(f"{field_name}必须是整数") from exc
    if str(value).strip() not in {str(number), f"{number}.0"}:
        raise CheckinDelaySettingsError(f"{field_name}必须是整数")
    if not 0 <= number <= MAX_DELAY_SECONDS:
        raise CheckinDelaySettingsError(
            f"{field_name}必须在 0～{MAX_DELAY_SECONDS} 秒之间"
        )
    return number


def normalize_checkin_delay_settings(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    result = {
        "xxqd_min_seconds": _integer(
            data.get("xxqd_min_seconds", DEFAULT_MIN_SECONDS),
            "小小签到最短等待时间",
        ),
        "xxqd_max_seconds": _integer(
            data.get("xxqd_max_seconds", DEFAULT_MAX_SECONDS),
            "小小签到最长等待时间",
        ),
        "class_cube_min_seconds": _integer(
            data.get("class_cube_min_seconds", DEFAULT_MIN_SECONDS),
            "班级魔方最短等待时间",
        ),
        "class_cube_max_seconds": _integer(
            data.get("class_cube_max_seconds", DEFAULT_MAX_SECONDS),
            "班级魔方最长等待时间",
        ),
    }
    if result["xxqd_min_seconds"] > result["xxqd_max_seconds"]:
        raise CheckinDelaySettingsError("小小签到最短等待时间不能大于最长等待时间")
    if result["class_cube_min_seconds"] > result["class_cube_max_seconds"]:
        raise CheckinDelaySettingsError("班级魔方最短等待时间不能大于最长等待时间")
    return result


def _read_settings(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckinDelaySettingsError("settings.json 读取失败") from exc
    if not isinstance(data, dict):
        raise CheckinDelaySettingsError("settings.json 必须是对象格式")
    return data


def load_checkin_delay_settings(path: Path = SETTINGS_FILE) -> dict:
    data = _read_settings(path)
    return normalize_checkin_delay_settings(data.get(SETTINGS_KEY))


def save_checkin_delay_settings(
    payload: dict,
    path: Path = SETTINGS_FILE,
) -> dict:
    normalized = normalize_checkin_delay_settings(payload)
    data = _read_settings(path)
    data[SETTINGS_KEY] = normalized
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
    return normalized


def get_checkin_delay_range(platform: str) -> tuple[int, int]:
    settings = load_checkin_delay_settings()
    if platform == "xxqd":
        return settings["xxqd_min_seconds"], settings["xxqd_max_seconds"]
    if platform == "class_cube":
        return (
            settings["class_cube_min_seconds"],
            settings["class_cube_max_seconds"],
        )
    raise CheckinDelaySettingsError("未知的签到平台")
