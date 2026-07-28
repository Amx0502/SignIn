from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .class_cube_client import QrSessionResult


class QrSessionCreate(BaseModel):
    account_id: int | None = Field(default=None, gt=0)


class ClassCubeAccountUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


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
