from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from .class_cube_client import QrSessionResult


class QrSessionCreate(BaseModel):
    account_id: int | None = Field(default=None, gt=0)


class ClassCubeAccountUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ManualCheckinRequest(BaseModel):
    notify_wecom: bool = False
    latitude: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )
    longitude: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )
    accuracy: float | None = Field(
        default=None,
        allow_inf_nan=False,
    )
    password: str = Field(default="", max_length=128)
    photo_path: str = Field(default="", max_length=512)


class ClassCubeTaskCreate(BaseModel):
    owner_user_id: int | None = Field(default=None, gt=0)
    account_id: int = Field(gt=0)
    course_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    poll_interval_seconds: int = 30
    latitude: float | None = Field(default=None, allow_inf_nan=False)
    longitude: float | None = Field(default=None, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    photo_path: str = Field(default="", max_length=512)
    password: str = Field(default="", max_length=255)
    schedule_times: list[str] = Field(default_factory=list, max_length=24)
    start_date: date | None = None
    end_date: date | None = None
    notify_wecom: bool = True


class ClassCubeTaskUpdate(BaseModel):
    account_id: int | None = Field(default=None, gt=0)
    course_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    latitude: float | None = Field(default=None, allow_inf_nan=False)
    longitude: float | None = Field(default=None, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    photo_path: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, max_length=255)
    clear_password: bool = False
    schedule_times: list[str] | None = Field(
        default=None, min_length=1, max_length=24
    )
    start_date: date | None = None
    end_date: date | None = None
    notify_wecom: bool | None = None


class ClassCubeTaskBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class ClassCubeSettingsUpdate(BaseModel):
    class_cube_webhook_url: str = Field(default="", max_length=2048)


def task_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "owner_user_id": task.get("owner_user_id"),
        "account_id": task.get("account_id"),
        "course_id": task.get("course_id"),
        "name": task.get("name", ""),
        "enabled": bool(task.get("enabled", False)),
        "poll_interval_seconds": 30,
        "latitude": task.get("latitude"),
        "longitude": task.get("longitude"),
        "accuracy": task.get("accuracy"),
        "photo_path": task.get("photo_path", ""),
        "schedule_times": task.get("schedule_times", []),
        "start_date": _iso(task.get("start_date")),
        "end_date": _iso(task.get("end_date")),
        "notify_wecom": bool(task.get("notify_wecom", True)),
        "has_password": bool(task.get("password")),
        "last_scan_at": _iso(task.get("last_scan_at")),
        "created_at": _iso(task.get("created_at")),
        "updated_at": _iso(task.get("updated_at")),
    }


def run_view(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _iso(value)
        for key, value in run.items()
        if key not in {"password", "cookie"}
    }


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def account_view(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account.get("id"),
        "owner_user_id": account.get("owner_user_id"),
        "name": account.get("name", ""),
        "remote_user_name": account.get("remote_user_name", ""),
        "status": account.get("status", "active"),
        "last_login_at": _iso(account.get("last_login_at")),
        "created_at": _iso(account.get("created_at")),
        "updated_at": _iso(account.get("updated_at")),
    }


def course_view(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": course.get("id"),
        "account_id": course.get("account_id"),
        "remote_course_id": course.get("remote_course_id", ""),
        "name": course.get("name", ""),
        "class_code": course.get("class_code", ""),
        "synced_at": _iso(course.get("synced_at")),
        "created_at": _iso(course.get("created_at")),
        "updated_at": _iso(course.get("updated_at")),
    }


def item_view(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "course_id": item.get("course_id"),
        "remote_item_id": item.get("remote_item_id", ""),
        "title": item.get("title", ""),
        "mode": item.get("mode", "unknown"),
        "remote_module": item.get("remote_module", ""),
        "status": item.get("status", "unknown"),
        "start_at": _iso(item.get("start_at")),
        "end_at": _iso(item.get("end_at")),
        "synced_at": _iso(item.get("synced_at")),
        "created_at": _iso(item.get("created_at")),
        "updated_at": _iso(item.get("updated_at")),
    }


def qr_result_view(result: QrSessionResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "retryable": bool(result.retryable),
    }
