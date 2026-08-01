from dataclasses import dataclass
from datetime import datetime
import math
import os
from pathlib import Path, PurePosixPath
import re
import time
from threading import RLock
from typing import Any, Callable
import uuid

from fastapi import UploadFile

from . import config
from .class_cube_client import (
    QR_TTL_SECONDS,
    ClassCubeClient,
    ClassCubeCookieExpired,
    ClassCubeRequestError,
    ClassCubeSubmissionUnknown,
    QrSessionNotFound,
)
from .class_cube_models import (
    account_view,
    course_view,
    item_view,
    qr_result_view,
    run_view,
    task_view,
)
from .class_cube_parser import ParsedForm
from .class_cube_repository import (
    ClassCubeNotFound,
    ClassCubeRepository,
)
from .class_cube_schedule import due_schedule_key, normalize_schedule_times
from .class_cube_notifier import ClassCubeNotifier
from .class_cube_settings import (
    ClassCubeSettingsError,
    load_class_cube_settings,
    save_class_cube_settings,
)


class ClassCubeValidationError(ValueError):
    pass


CLASS_CUBE_PHOTO_MAX_BYTES = 10 * 1024 * 1024
CLASS_CUBE_PHOTO_CHUNK_BYTES = 64 * 1024
AUTOCHECK_GPS_PHOTO_RES = (
    "s46grRvFJukcJc3CFnqHcKQLxAvxJYJ-"
    "Uh8bsD1YcXiVMN-MoqkVmZPDzpUhTMyf"
)
_PHOTO_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _photo_signature(extension: str, header: bytes) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return (
            len(header) >= 12
            and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
        )
    return False


def _reject_symlink_components(*paths: Path) -> None:
    try:
        if any(path.is_symlink() for path in paths):
            raise ClassCubeValidationError(
                "签到照片路径无效"
            )
    except OSError as exc:
        raise ClassCubeValidationError(
            "签到照片路径无效"
        ) from exc


def _path_is_contained(path: Path, root: Path) -> bool:
    try:
        return (
            os.path.commonpath([str(path), str(root)])
            == str(root)
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class CheckinParameters:
    latitude: float | None = None
    longitude: float | None = None
    accuracy: float | None = None
    password: str = ""


def _number_text(value: float) -> str:
    return format(float(value), ".15g")


def _validated_number(
    value: float | None,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    if value is None:
        raise ClassCubeValidationError(f"请填写{label}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ClassCubeValidationError(
            f"{label}格式无效"
        ) from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ClassCubeValidationError(f"{label}超出有效范围")
    return number


def build_submission_fields(
    form: ParsedForm,
    parameters: CheckinParameters,
    remote_item_id: str = "",
    remote_photo_value: str = "",
) -> dict[str, str]:
    if form.mode not in {
        "qr",
        "gps",
        "gps_photo",
        "password",
    }:
        raise ClassCubeValidationError(
            "无法识别该签到项的提交方式"
        )

    fields: dict[str, str] = {}
    if form.item_id_field:
        fields[form.item_id_field] = str(remote_item_id)

    if form.mode == "qr":
        return fields

    if form.mode == "password":
        if not form.password_field:
            raise ClassCubeValidationError(
                "无法识别签到密码字段"
            )
        if not parameters.password:
            raise ClassCubeValidationError("请填写签到密码")
        fields[form.password_field] = parameters.password
        return fields

    if form.mode in {"gps", "gps_photo"}:
        if not form.latitude_field or not form.longitude_field:
            raise ClassCubeValidationError(
                "无法识别完整位置字段"
            )
        latitude = _validated_number(
            parameters.latitude,
            "纬度",
            -90,
            90,
        )
        longitude = _validated_number(
            parameters.longitude,
            "经度",
            -180,
            180,
        )
        fields[form.latitude_field] = _number_text(latitude)
        fields[form.longitude_field] = _number_text(longitude)
        if form.accuracy_field:
            accuracy = _validated_number(
                parameters.accuracy,
                "定位精度",
                0,
                1_000_000,
            )
            fields[form.accuracy_field] = _number_text(accuracy)
        if form.gps_address_field:
            fields[form.gps_address_field] = ""

    if form.mode == "gps_photo" and form.photo_resource_field:
        remote_value = str(
            form.hidden_fields.get(form.photo_resource_field) or ""
        ).strip()
        supplied_value = str(remote_photo_value or "").strip()
        if supplied_value:
            fields[form.photo_resource_field] = supplied_value
        elif not remote_value:
            fields[form.photo_resource_field] = (
                AUTOCHECK_GPS_PHOTO_RES
            )
    return fields


def _eligible_task_items(
    task: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    has_password = bool(str(task.get("password") or "").strip())
    has_coordinates = (
        task.get("latitude") not in (None, "")
        and task.get("longitude") not in (None, "")
    )
    eligible = []
    for item in items:
        mode = str(item.get("mode") or "unknown")
        if mode == "password" and not has_password:
            continue
        if mode in {"gps", "gps_photo"} and not has_coordinates:
            continue
        eligible.append(item)
    return eligible


class ClassCubeRemoteError(RuntimeError):
    status_code = 502

    def __init__(
        self,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        retryable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.data = data or {}
        self.retryable = retryable


@dataclass(frozen=True)
class _QrTarget:
    owner_user_id: int
    account_id: int | None
    expires_at: float


class ClassCubeService:
    def __init__(
        self,
        repository: ClassCubeRepository,
        client: ClassCubeClient,
        logger,
        clock: Callable[[], float] | None = None,
        notifier: ClassCubeNotifier | None = None,
    ):
        self.repository = repository
        self.client = client
        self.logger = logger
        self._clock = clock or time.monotonic
        self.notifier = notifier or ClassCubeNotifier()
        self._qr_targets: dict[str, _QrTarget] = {}
        self._qr_lock = RLock()
        self._execution_lock = RLock()
        self._running_task_ids: set[int] = set()
        self._closed = False

    def _pop_expired_targets(
        self,
        now: float,
    ) -> dict[str, _QrTarget]:
        with self._qr_lock:
            expired = {
                token: target
                for token, target in self._qr_targets.items()
                if now >= target.expires_at
            }
            for token in expired:
                self._qr_targets.pop(token, None)
        return expired

    def _cancel_targets(
        self,
        targets: dict[str, _QrTarget],
    ) -> None:
        for token, target in targets.items():
            self.client.cancel_qr_session(
                token,
                target.owner_user_id,
            )

    def _cleanup_expired_targets(
        self,
        now: float,
    ) -> dict[str, _QrTarget]:
        expired = self._pop_expired_targets(now)
        self._cancel_targets(expired)
        return expired

    @staticmethod
    def _actor_scope(actor: dict[str, Any]) -> tuple[int, bool]:
        try:
            actor_user_id = int(actor["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ClassCubeValidationError(
                "当前用户信息无效"
            ) from exc
        return actor_user_id, actor.get("role") == "admin"

    def _log_remote_failure(
        self,
        operation: str,
        exc: BaseException,
    ) -> None:
        self.logger.warning(
            "班级魔方%s失败（%s）",
            operation,
            type(exc).__name__,
        )

    def _remote_error(
        self,
        operation: str,
        exc: BaseException,
        *,
        data: dict[str, Any] | None = None,
    ) -> ClassCubeRemoteError:
        self._log_remote_failure(operation, exc)
        return ClassCubeRemoteError(
            f"班级魔方{operation}失败，请稍后重试",
            data=data,
            retryable=True,
        )

    def _cookie_expired_error(
        self,
        exc: BaseException,
        *,
        data: dict[str, Any] | None = None,
    ) -> ClassCubeRemoteError:
        self._log_remote_failure("验证登录状态", exc)
        return ClassCubeRemoteError(
            "班级魔方登录已失效，请重新扫码",
            data=data,
            retryable=False,
        )

    def list_accounts(
        self,
        actor: dict[str, Any],
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        effective_owner = owner_user_id if is_admin else None
        accounts = self.repository.list_accounts(
            actor_user_id,
            is_admin,
            owner_user_id=effective_owner,
        )
        return [account_view(account) for account in accounts]

    def get_account(
        self,
        account_id: int,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        actor_user_id, is_admin = self._actor_scope(actor)
        return account_view(
            self.repository.get_account(
                account_id,
                actor_user_id,
                is_admin,
            )
        )

    def create_qr_session(
        self,
        actor: dict[str, Any],
        account_id: int | None = None,
    ) -> dict[str, Any]:
        actor_user_id, is_admin = self._actor_scope(actor)
        self._cleanup_expired_targets(self._clock())
        with self._qr_lock:
            if self._closed:
                raise ClassCubeValidationError(
                    "班级魔方服务已关闭"
                )
        if account_id is not None:
            self.repository.get_account(
                account_id,
                actor_user_id,
                is_admin,
            )
        try:
            created = self.client.create_qr_session(actor_user_id)
        except ClassCubeRequestError as exc:
            raise self._remote_error("创建扫码会话", exc) from exc
        try:
            with self._qr_lock:
                if self._closed:
                    raise ClassCubeValidationError(
                        "班级魔方服务已关闭"
                    )
                if account_id is not None:
                    self.repository.get_account(
                        account_id,
                        actor_user_id,
                        is_admin,
                    )
                self._qr_targets[created.token] = _QrTarget(
                    owner_user_id=actor_user_id,
                    account_id=account_id,
                    expires_at=(
                        self._clock() + QR_TTL_SECONDS
                    ),
                )
        except Exception:
            self.client.cancel_qr_session(
                created.token,
                actor_user_id,
            )
            raise
        return {
            "token": created.token,
            "qr_image": (
                "data:image/png;base64,"
                f"{created.qr_image_base64}"
            ),
            "expires_in_seconds": 120,
        }

    def poll_qr_session(
        self,
        token: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        actor_user_id, is_admin = self._actor_scope(actor)
        expired = self._cleanup_expired_targets(self._clock())
        expired_target = expired.get(token)
        if expired_target is not None:
            if expired_target.owner_user_id != actor_user_id:
                raise ClassCubeNotFound(
                    "扫码会话不存在或已失效"
                )
            return {
                "status": "expired",
                "retryable": False,
            }
        with self._qr_lock:
            target = self._qr_targets.get(token)
        if (
            target is None
            or target.owner_user_id != actor_user_id
        ):
            raise ClassCubeNotFound("扫码会话不存在或已失效")

        try:
            result = self.client.poll_qr_session(
                token,
                actor_user_id,
            )
        except QrSessionNotFound as exc:
            with self._qr_lock:
                self._qr_targets.pop(token, None)
            raise ClassCubeNotFound(
                "扫码会话不存在或已失效"
            ) from exc

        if result.status != "success":
            if (
                result.status in {"expired", "error"}
                and not result.retryable
            ):
                with self._qr_lock:
                    self._qr_targets.pop(token, None)
            return qr_result_view(result)

        with self._qr_lock:
            self._qr_targets.pop(token, None)
        if not result.cookie:
            raise ClassCubeRemoteError(
                "班级魔方扫码结果无有效登录凭据",
                retryable=False,
            )

        account = self.repository.upsert_scanned_account(
            owner_user_id=actor_user_id,
            identity={},
            cookie=result.cookie,
            account_id=target.account_id,
            actor_user_id=actor_user_id,
            is_admin=is_admin,
        )
        safe_account = account_view(account)

        try:
            remote_user_name = self.client.fetch_student_name(
                result.cookie
            )
            if remote_user_name:
                account = self.repository.upsert_scanned_account(
                    owner_user_id=account["owner_user_id"],
                    identity={
                        "remote_user_name": remote_user_name
                    },
                    cookie=result.cookie,
                    account_id=account["id"],
                    actor_user_id=actor_user_id,
                    is_admin=is_admin,
                )
                safe_account = account_view(account)
            courses = self.client.fetch_courses(result.cookie)
        except ClassCubeCookieExpired as exc:
            raise self._cookie_expired_error(
                exc,
                data={
                    "account": safe_account,
                    "retryable": False,
                },
            ) from exc
        except ClassCubeRequestError as exc:
            sync_warning = "扫码登录成功，但账号资料同步暂时失败，可在账号管理中重试"
            self.logger.warning("班级魔方扫码账号资料同步失败（%s）", type(exc).__name__)
            return {
                "status": "success",
                "retryable": True,
                "account": safe_account,
                "sync_warning": sync_warning,
                "courses": [],
            }

        stored_courses = self.repository.upsert_courses(
            account["id"],
            courses,
            actor_user_id,
            is_admin,
        )
        return {
            "status": "success",
            "retryable": False,
            "account": safe_account,
            "courses": [
                course_view(course)
                for course in stored_courses
            ],
        }

    def update_account(
        self,
        account_id: int,
        payload: dict[str, Any],
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        actor_user_id, is_admin = self._actor_scope(actor)
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ClassCubeValidationError("账号备注不能为空")
        if len(name) > 255:
            raise ClassCubeValidationError(
                "账号备注不能超过 255 个字符"
            )
        account = self.repository.update_account_name(
            account_id,
            name,
            actor_user_id,
            is_admin,
        )
        return account_view(account)

    def delete_account(
        self,
        account_id: int,
        actor: dict[str, Any],
    ) -> bool:
        actor_user_id, is_admin = self._actor_scope(actor)
        with self._qr_lock:
            self.repository.delete_account(
                account_id,
                actor_user_id,
                is_admin,
            )
            cancelled_targets = {
                token: target
                for token, target in self._qr_targets.items()
                if target.account_id == account_id
            }
            for token in cancelled_targets:
                self._qr_targets.pop(token, None)
        self._cancel_targets(cancelled_targets)
        return True

    def batch_delete_accounts(
        self,
        account_ids: list[int],
        actor: dict[str, Any],
    ) -> int:
        normalized_ids = sorted(set(account_ids))
        actor_user_id, is_admin = self._actor_scope(actor)
        with self._qr_lock:
            deleted = self.repository.delete_accounts(
                normalized_ids,
                actor_user_id,
                is_admin,
            )
            deleted_ids = set(normalized_ids)
            cancelled_targets = {
                token: target
                for token, target in self._qr_targets.items()
                if target.account_id in deleted_ids
            }
            for token in cancelled_targets:
                self._qr_targets.pop(token, None)
        self._cancel_targets(cancelled_targets)
        return deleted

    def close(self) -> None:
        with self._qr_lock:
            if self._closed:
                return
            self._closed = True
            self._qr_targets.clear()
        self.client.close()

    def sync_courses(
        self,
        account_id: int,
        actor: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        account = self.repository.get_account(
            account_id,
            actor_user_id,
            is_admin,
        )
        try:
            courses = self.client.fetch_courses(account["cookie"])
        except ClassCubeCookieExpired as exc:
            marker = getattr(
                self.repository, "mark_account_expired", None
            )
            if marker is not None:
                marker(account_id, actor_user_id, is_admin)
            raise self._cookie_expired_error(exc) from exc
        except ClassCubeRequestError as exc:
            raise self._remote_error("同步课程", exc) from exc
        stored = self.repository.upsert_courses(
            account_id,
            courses,
            actor_user_id,
            is_admin,
        )
        return [course_view(course) for course in stored]

    def list_courses(
        self,
        account_id: int,
        actor: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        courses = self.repository.list_courses(
            account_id,
            actor_user_id,
            is_admin,
        )
        return [course_view(course) for course in courses]

    def sync_items(
        self,
        course_id: int,
        actor: dict[str, Any],
        *,
        latest_only: bool = False,
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        course = self.repository.get_course(
            course_id,
            actor_user_id,
            is_admin,
        )
        account = self.repository.get_account(
            course["account_id"],
            actor_user_id,
            is_admin,
        )

        successful_sources = 0
        last_error: ClassCubeRequestError | None = None
        for module in ("punchs", "daka"):
            try:
                bundles = self.client.fetch_items(
                    account["cookie"],
                    course["remote_course_id"],
                    module=module,
                )
            except ClassCubeCookieExpired as exc:
                marker = getattr(
                    self.repository, "mark_account_expired", None
                )
                if marker is not None:
                    marker(
                        account["id"], actor_user_id, is_admin
                    )
                raise self._cookie_expired_error(exc) from exc
            except ClassCubeRequestError as exc:
                last_error = exc
                self._log_remote_failure(
                    f"同步{module}签到项",
                    exc,
                )
                continue
            sync_source = getattr(
                self.repository, "sync_source_items", None
            )
            if sync_source is not None:
                sync_source(
                    course_id, module, bundles,
                    actor_user_id, is_admin,
                )
            else:
                self.repository.upsert_items(
                    course_id, bundles, actor_user_id, is_admin
                )
            successful_sources += 1
        if successful_sources == 0:
            raise ClassCubeRemoteError(
                "班级魔方签到项同步失败，请稍后重试",
                retryable=True,
            ) from last_error
        return self.list_items(
            course_id,
            actor,
            latest_only=latest_only,
        )

    def list_tasks(self, actor, owner_user_id=None):
        actor_user_id, is_admin = self._actor_scope(actor)
        if not is_admin and owner_user_id not in (None, actor_user_id):
            raise ClassCubeNotFound("班级魔方任务不存在")
        return [
            task_view(task)
            for task in self.repository.list_tasks(
                actor_user_id, is_admin, owner_user_id
            )
        ]

    def create_task(self, payload, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        values = dict(payload)
        values = self._validate_task_schedule(values)
        values["poll_interval_seconds"] = 30
        try:
            row = self.repository.save_task(
                values, actor_user_id, is_admin
            )
        except ValueError as exc:
            raise ClassCubeValidationError(str(exc)) from exc
        return task_view(row)

    def update_task(self, task_id, payload, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        current = self.repository.get_task(
            task_id, actor_user_id, is_admin
        )
        values = dict(current)
        supplied = dict(payload)
        if supplied.pop("clear_password", False):
            values["password"] = ""
        elif supplied.get("password") is None:
            supplied.pop("password", None)
        values.update(supplied)
        values = self._validate_task_schedule(values)
        values["poll_interval_seconds"] = 30
        try:
            row = self.repository.save_task(
                values, actor_user_id, is_admin, task_id=task_id
            )
        except ValueError as exc:
            raise ClassCubeValidationError(str(exc)) from exc
        return task_view(row)

    def delete_task(self, task_id, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        self.repository.delete_tasks([task_id], actor_user_id, is_admin)
        return True

    def batch_delete_tasks(self, task_ids, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        return self.repository.delete_tasks(
            task_ids, actor_user_id, is_admin
        )

    def list_due_tasks(self):
        now = datetime.now()
        due = []
        for task in self.repository.list_tasks(
            0, True, enabled=True
        ):
            schedule_key = due_schedule_key(task, now)
            if schedule_key:
                due.append({**task, "_schedule_key": schedule_key})
        return due

    def reserve_task_scan(self, task_id, schedule_key=None):
        if schedule_key:
            return self.repository.claim_task_schedule(
                task_id, schedule_key
            )
        return True

    @staticmethod
    def _validate_task_schedule(values):
        normalized = normalize_schedule_times(
            values.get("schedule_times", [])
        )
        if not normalized:
            raise ClassCubeValidationError(
                "请至少添加一个执行时间"
            )
        start = values.get("start_date")
        end = values.get("end_date")
        if start and end and start > end:
            raise ClassCubeValidationError(
                "开始日期不能晚于结束日期"
            )
        values["schedule_times"] = normalized
        values["notify_wecom"] = bool(
            values.get("notify_wecom", True)
        )
        return values

    def get_settings(self, actor):
        _, is_admin = self._actor_scope(actor)
        try:
            settings = load_class_cube_settings()
        except ClassCubeSettingsError as exc:
            raise ClassCubeValidationError(str(exc)) from exc
        if not is_admin:
            settings.pop("class_cube_webhook_url", None)
        return settings

    def update_settings(self, payload, actor):
        _, is_admin = self._actor_scope(actor)
        if not is_admin:
            raise ClassCubeNotFound("班级魔方设置不存在")
        try:
            return save_class_cube_settings(
                payload.get("class_cube_webhook_url", "")
            )
        except ClassCubeSettingsError as exc:
            raise ClassCubeValidationError(str(exc)) from exc

    @staticmethod
    def _task_actor(task):
        return {
            "id": int(task["owner_user_id"]),
            "role": "user",
        }

    @staticmethod
    def _trigger_name(trigger):
        return {
            "manual": "手动执行",
            "scheduled": "定时执行",
        }.get(str(trigger), "自动执行")

    @staticmethod
    def _mode_name(mode):
        return {
            "qr": "二维码签到",
            "gps": "GPS 签到",
            "gps_photo": "GPS+拍照签到",
            "password": "密码签到",
        }.get(str(mode), "未知签到类型")

    @staticmethod
    def _status_name(status):
        return {
            "success": "签到成功",
            "already_signed": "已完成，无需重复签到",
            "waiting_parameter": "缺少签到参数",
            "unknown_result": "结果待人工确认",
            "not_started": "签到尚未开始",
            "skipped": "无需提交",
            "failed": "签到失败",
        }.get(str(status), "执行完成")

    @staticmethod
    def _task_parameters(task):
        def coordinate(value):
            if value in (None, ""):
                return None
            return format(float(value), ".7f")

        return {
            "longitude": coordinate(task.get("longitude")),
            "latitude": coordinate(task.get("latitude")),
            "image_count": 0,
            "password": (
                "configured"
                if task.get("password")
                else ""
            ),
        }

    @staticmethod
    def _parameter_log_parts(parameters):
        parts = []
        longitude = parameters.get("longitude")
        latitude = parameters.get("latitude")
        if longitude is not None and latitude is not None:
            parts.append(f"坐标：{longitude}, {latitude}")
        parts.append(
            f"图片：{int(parameters.get('image_count') or 0)}张"
        )
        password = parameters.get("password")
        if password:
            parts.append("密码：已配置")
        return parts

    def execute_task(self, task_id, trigger="scheduled"):
        task_id = int(task_id)
        with self._execution_lock:
            if task_id in self._running_task_ids:
                return {
                    "task_id": task_id,
                    "status": "running",
                    "message": "该任务正在执行",
                    "scanned": 0,
                    "success": 0,
                    "already_signed": 0,
                    "skipped": 0,
                    "failed": 0,
                    "unknown": 0,
                    "details": [],
                }
            self._running_task_ids.add(task_id)
        started_at = datetime.now()
        try:
            task = self.repository.get_task(task_id, 0, True)
        except ClassCubeNotFound:
            with self._execution_lock:
                self._running_task_ids.discard(task_id)
            raise
        if trigger == "scheduled" and not task.get("enabled"):
            with self._execution_lock:
                self._running_task_ids.discard(task_id)
            return {
                "task_id": task_id,
                "task_name": task.get("name", ""),
                "status": "disabled",
                "message": "任务已停用",
                "scanned": 0,
                "success": 0,
                "already_signed": 0,
                "skipped": 1,
                "failed": 0,
                "unknown": 0,
                "details": [],
            }
        actor = self._task_actor(task)
        try:
            account = self.repository.get_account(
                task["account_id"], task["owner_user_id"], False
            )
            course = self.repository.get_course(
                task["course_id"], task["owner_user_id"], False
            )
        except Exception:
            with self._execution_lock:
                self._running_task_ids.discard(task_id)
            raise
        if account.get("status") != "active":
            result = {
                "task_id": task_id,
                "task_name": task.get("name", ""),
                "status": "failed",
                "message": "班级魔方登录已失效，请重新扫码",
                "scanned": 0,
                "success": 0,
                "already_signed": 0,
                "skipped": 0,
                "failed": 1,
                "unknown": 0,
                "details": [],
            }
            self.repository.record_task_run(
                task_id, "failed", result["message"], result, started_at
            )
            with self._execution_lock:
                self._running_task_ids.discard(task_id)
            return result
        result = {
            "task_id": task_id,
            "task_name": task.get("name", ""),
            "status": "pending",
            "message": "",
            "scanned": 0,
            "success": 0,
            "already_signed": 0,
            "skipped": 0,
            "failed": 0,
            "unknown": 0,
            "details": [],
        }
        task_parameters = self._task_parameters(task)
        notification = {
            **result,
            "account_name": (
                account.get("name")
                or account.get("remote_user_name")
                or "-"
            ),
            "course_name": course.get("name", "-"),
            "trigger": trigger,
            "started_at": started_at,
            "parameters": task_parameters,
        }
        self.logger.info(
            "开始%s任务「%s」；账号：%s；课程：%s",
            self._trigger_name(trigger),
            task.get("name", ""),
            notification["account_name"],
            notification["course_name"],
        )
        try:
            items = self.sync_items(task["course_id"], actor)
            active_items = [
                item for item in items
                if item.get("status") == "active"
            ]
            result["scanned"] = len(active_items)
            self.logger.info(
                "签到项扫描完成：发现 %s 个可执行签到项",
                len(active_items),
            )
            if not active_items:
                result["status"] = "no_sign_in"
                result["message"] = "当前课程没有可执行签到项"
                self.repository.record_task_run(
                    task_id,
                    "no_sign_in",
                    result["message"],
                    result,
                    started_at,
                )
                self.logger.info(
                    "任务「%s」执行完成：当前课程没有可执行签到项",
                    task.get("name", ""),
                )
                return result
            eligible_items = _eligible_task_items(
                task,
                active_items,
            )
            result["skipped"] += (
                len(active_items) - len(eligible_items)
            )
            for item in eligible_items:
                current = self.repository.get_task(task_id, 0, True)
                if (
                    trigger == "scheduled"
                    and not current.get("enabled")
                ):
                    break
                claim = self.repository.try_claim(
                    task_id,
                    item["id"],
                    item["remote_item_id"],
                    item["remote_module"],
                )
                if not claim:
                    result["skipped"] += 1
                    continue
                checkin_result = self.manual_checkin(
                    item["id"],
                    {
                        "latitude": task.get("latitude"),
                        "longitude": task.get("longitude"),
                        "accuracy": task.get("accuracy"),
                        "password": task.get("password") or "",
                    },
                    actor,
                    before_submit=lambda: self._mark_automatic_submitting(
                        claim
                    ),
                )
                status = checkin_result["status"]
                if status == "success":
                    result["success"] += 1
                elif status == "already_signed":
                    result["already_signed"] += 1
                elif status == "unknown_result":
                    result["unknown"] += 1
                elif status in {"waiting_parameter", "not_started"}:
                    result["skipped"] += 1
                else:
                    result["failed"] += 1
                detail = {
                    "item_id": item["id"],
                    "title": item.get("title", "签到项"),
                    "mode": item.get("mode", "unknown"),
                    "status": status,
                    "message": checkin_result.get("message", ""),
                    "executed_at": datetime.now().strftime("%H:%M:%S"),
                }
                result["details"].append(detail)
                parameter_text = "；".join(
                    self._parameter_log_parts(task_parameters)
                )
                self.logger.info(
                    "签到项「%s」；类型：%s；%s；结果：%s",
                    detail["title"],
                    self._mode_name(detail["mode"]),
                    parameter_text,
                    self._status_name(status),
                )
                state = {
                    "success": "succeeded",
                    "already_signed": "already_signed",
                    "unknown_result": "unknown",
                }.get(status, "retryable")
                self.repository.finish_claim(
                    claim["id"],
                    task_id,
                    item["id"],
                    item["remote_item_id"],
                    item["remote_module"],
                    state,
                    status,
                    checkin_result.get("message", ""),
                    item.get("mode", "unknown"),
                    expected_lease_token=claim["lease_token"],
                    started_at=claim["started_at"],
                )
            if result["failed"]:
                result["status"] = "failed"
                result["message"] = "部分或全部签到执行失败"
            elif result["unknown"]:
                result["status"] = "unknown_result"
                result["message"] = "签到结果需要人工确认"
            elif waiting_detail := next(
                (
                    detail
                    for detail in result["details"]
                    if detail["status"] == "waiting_parameter"
                ),
                None,
            ):
                result["status"] = "waiting_parameter"
                result["message"] = (
                    waiting_detail.get("message")
                    or "签到任务缺少必要参数"
                )
            elif result["success"]:
                result["status"] = "success"
                result["message"] = "签到执行成功"
            elif result["already_signed"]:
                result["status"] = "already_signed"
                result["message"] = "签到已经完成"
            else:
                result["status"] = "skipped"
                result["message"] = "当前没有需要提交的签到项"
            self.logger.info(
                "任务「%s」执行完成：成功 %s 项，已完成 %s 项，"
                "跳过 %s 项，失败 %s 项，待确认 %s 项",
                task.get("name", ""),
                result["success"],
                result["already_signed"],
                result["skipped"],
                result["failed"],
                result["unknown"],
            )
            return result
        except Exception as exc:
            result["status"] = "failed"
            result["message"] = "班级魔方任务执行失败"
            result["failed"] += 1
            result["details"].append(
                {
                    "title": "任务执行",
                    "mode": "task",
                    "status": "failed",
                    "message": type(exc).__name__,
                }
            )
            self.repository.record_task_run(
                task_id,
                "failed",
                result["message"],
                result,
                started_at,
            )
            self.logger.error(
                "任务「%s」执行失败：%s",
                task.get("name", ""),
                type(exc).__name__,
            )
            return result
        finally:
            notification.update(result)
            self._send_task_notification(task, notification)
            with self._execution_lock:
                self._running_task_ids.discard(task_id)

    def run_scheduled_task(self, task_id):
        return self.execute_task(task_id, trigger="scheduled")

    def _send_task_notification(self, task, summary):
        if not task.get("notify_wecom", True):
            return
        try:
            webhook_url = load_class_cube_settings().get(
                "class_cube_webhook_url", ""
            )
            if not webhook_url:
                self.logger.info(
                    "任务「%s」未发送企业微信通知：机器人未配置",
                    task.get("name", ""),
                )
                return
            self.notifier.send_summary(webhook_url, summary)
            self.logger.info(
                "任务「%s」企业微信通知发送成功",
                task.get("name", ""),
            )
        except Exception as exc:
            self.logger.error(
                "任务「%s」企业微信通知发送失败：%s",
                task.get("name", ""),
                type(exc).__name__,
            )

    def _mark_automatic_submitting(self, claim):
        if not self.repository.mark_claim_submitting(
            claim["id"], claim["lease_token"]
        ):
            raise ClassCubeValidationError("签到声明租约已失效")

    def list_runs(self, actor, **filters):
        actor_user_id, is_admin = self._actor_scope(actor)
        owner_user_id = filters.get("owner_user_id")
        if not is_admin and owner_user_id not in (None, actor_user_id):
            raise ClassCubeNotFound("班级魔方运行记录不存在")
        return [
            run_view(row)
            for row in self.repository.list_runs(
                actor_user_id, is_admin, **filters
            )
        ]

    def confirm_claim_retry(self, claim_id, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        try:
            return self.repository.confirm_claim_retry(
                claim_id, actor_user_id, is_admin
            )
        except ValueError as exc:
            raise ClassCubeValidationError(str(exc)) from exc

    def list_items(
        self,
        course_id: int,
        actor: dict[str, Any],
        *,
        latest_only: bool = False,
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        items = self.repository.list_items(
            course_id,
            actor_user_id,
            is_admin,
            latest_only=latest_only,
        )
        return [item_view(item) for item in items]

    @staticmethod
    def _stored_form(item: dict[str, Any]) -> ParsedForm:
        schema = item.get("form_schema")
        if not isinstance(schema, dict):
            schema = {}
        return ParsedForm(
            action=str(item.get("form_action") or ""),
            method=str(schema.get("method") or "get"),
            mode=str(
                schema.get("mode")
                or item.get("mode")
                or "unknown"
            ),
            hidden_fields=dict(
                schema.get("hidden_fields")
                if isinstance(
                    schema.get("hidden_fields"),
                    dict,
                )
                else {}
            ),
            password_field=str(
                schema.get("password_field") or ""
            ),
            file_field=str(schema.get("file_field") or ""),
            item_id_field=str(
                schema.get("item_id_field") or ""
            ),
            latitude_field=str(
                schema.get("latitude_field") or ""
            ),
            longitude_field=str(
                schema.get("longitude_field") or ""
            ),
            accuracy_field=str(
                schema.get("accuracy_field") or ""
            ),
            gps_address_field=str(
                schema.get("gps_address_field") or ""
            ),
            photo_resource_field=str(
                schema.get("photo_resource_field") or ""
            ),
            submit_capable=bool(
                schema.get("submit_capable", False)
            ),
            upload_action=str(
                schema.get("upload_action") or ""
            ),
            upload_method=str(
                schema.get("upload_method") or ""
            ),
            upload_file_field=str(
                schema.get("upload_file_field") or ""
            ),
            upload_response_key=str(
                schema.get("upload_response_key") or ""
            ),
        )

    @staticmethod
    def _checkin_view(
        status: str,
        message: str,
    ) -> dict[str, str]:
        safe_message = " ".join(str(message).split())[:200]
        return {
            "status": status,
            "message": safe_message,
        }

    def _mark_account_expired(
        self,
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> None:
        self.repository.mark_account_expired(
            account_id,
            actor_user_id,
            is_admin,
        )

    def _manual_checkin_context(self, item_id, actor):
        actor_user_id, is_admin = self._actor_scope(actor)
        item = self.repository.get_item(
            item_id,
            actor_user_id,
            is_admin,
        )
        course = self.repository.get_course(
            item["course_id"],
            actor_user_id,
            is_admin,
        )
        account = self.repository.get_account(
            course["account_id"],
            actor_user_id,
            is_admin,
        )
        return {
            "actor_user_id": actor_user_id,
            "is_admin": is_admin,
            "item": item,
            "course": course,
            "account": account,
        }

    def _refresh_manual_context(self, item_id, actor, context):
        self.sync_items(context["course"]["id"], actor)
        return self._manual_checkin_context(item_id, actor)

    def _confirm_unknown_submission(self, context, actor) -> bool:
        item = context["item"]
        try:
            items = self.sync_items(context["course"]["id"], actor)
        except ClassCubeRemoteError:
            return False
        return any(
            str(candidate.get("remote_item_id") or "")
            == str(item.get("remote_item_id") or "")
            and str(candidate.get("remote_module") or "")
            == str(item.get("remote_module") or "")
            and candidate.get("status") == "closed"
            for candidate in items
        )

    @staticmethod
    def _manual_parameters(payload):
        return {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "image_count": 0,
            "password": (
                "configured"
                if payload.get("password")
                else ""
            ),
        }

    def _manual_summary(
        self,
        context,
        result,
        payload,
        started_at,
    ):
        item = context["item"]
        course = context["course"]
        account = context["account"]
        status = result.get("status", "failed")
        return {
            "status": status,
            "message": result.get("message", ""),
            "success": 1 if status == "success" else 0,
            "already_signed": 1 if status == "already_signed" else 0,
            "failed": (
                0 if status in {"success", "already_signed"} else 1
            ),
            "unknown": 0,
            "details": [
                {
                    "item_id": item["id"],
                    "title": item.get("title", "签到项"),
                    "mode": item.get("mode", "unknown"),
                    "status": status,
                    "message": result.get("message", ""),
                    "executed_at": datetime.now().strftime("%H:%M:%S"),
                }
            ],
            "account_name": (
                account.get("name")
                or account.get("remote_user_name")
                or "-"
            ),
            "course_name": course.get("name", "-"),
            "trigger": "course_manual",
            "started_at": started_at.isoformat(),
            "parameters": self._manual_parameters(payload),
        }

    def _record_manual_run(self, context, summary, started_at):
        item = context["item"]
        course = context["course"]
        account = context["account"]
        self.repository.record_manual_run(
            owner_user_id=int(account["owner_user_id"]),
            account_id=int(account["id"]),
            course_id=int(course["id"]),
            checkin_item_id=int(item["id"]),
            remote_item_id=item.get("remote_item_id", ""),
            mode=item.get("mode", "unknown"),
            status=summary.get("status", "failed"),
            message=summary.get("message", ""),
            response_summary=summary,
            started_at=started_at,
        )

    def _send_manual_notification(self, summary):
        try:
            webhook_url = load_class_cube_settings().get(
                "class_cube_webhook_url", ""
            )
            if not webhook_url:
                self.logger.info(
                    "课程手动签到未发送企业微信通知：机器人未配置"
                )
                return
            self.notifier.send_summary(webhook_url, summary)
            self.logger.info(
                "课程手动签到企业微信通知发送成功"
            )
        except Exception as exc:
            self.logger.error(
                "课程手动签到企业微信通知发送失败：%s",
                type(exc).__name__,
            )

    def tracked_manual_checkin(self, item_id, payload, actor):
        started_at = datetime.now()
        context = self._manual_checkin_context(item_id, actor)
        item = context["item"]
        course = context["course"]
        account = context["account"]
        parameters = self._manual_parameters(payload)
        parameter_text = "；".join(
            self._parameter_log_parts(parameters)
        )
        self.logger.info(
            "开始课程手动签到；账号：%s；课程：%s；"
            "签到项：%s；类型：%s；%s",
            (
                account.get("name")
                or account.get("remote_user_name")
                or "-"
            ),
            course.get("name", "-"),
            item.get("title", "签到项"),
            self._mode_name(item.get("mode", "unknown")),
            parameter_text,
        )
        try:
            result = self.manual_checkin(
                item_id,
                payload,
                actor,
                context=context,
            )
        except Exception as exc:
            failed_result = self._checkin_view(
                "failed",
                "课程手动签到执行失败",
            )
            summary = self._manual_summary(
                context,
                failed_result,
                payload,
                started_at,
            )
            self._record_manual_run(context, summary, started_at)
            self.logger.error(
                "课程手动签到失败；账号：%s；签到项：%s；异常：%s",
                (
                    account.get("name")
                    or account.get("remote_user_name")
                    or "-"
                ),
                item.get("title", "签到项"),
                type(exc).__name__,
            )
            if payload.get("notify_wecom", False):
                self._send_manual_notification(summary)
            raise

        summary = self._manual_summary(
            context,
            result,
            payload,
            started_at,
        )
        self._record_manual_run(context, summary, started_at)
        self.logger.info(
            "课程手动签到完成；账号：%s；签到项：%s；结果：%s",
            (
                account.get("name")
                or account.get("remote_user_name")
                or "-"
            ),
            item.get("title", "签到项"),
            self._status_name(result.get("status")),
        )
        if payload.get("notify_wecom", False):
            self._send_manual_notification(summary)
        return result

    def manual_checkin(
        self,
        item_id: int,
        payload: dict[str, Any],
        actor: dict[str, Any],
        before_submit: Callable[[], None] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        if context is None:
            context = self._manual_checkin_context(item_id, actor)
        if before_submit is None:
            context = self._refresh_manual_context(
                item_id,
                actor,
                context,
            )
        actor_user_id = context["actor_user_id"]
        is_admin = context["is_admin"]
        item = context["item"]
        course = context["course"]
        account = context["account"]
        if account.get("status") != "active":
            return self._checkin_view(
                "failed",
                "班级魔方登录已失效，请重新扫码",
            )

        form = self._stored_form(item)
        if (
            not form.submit_capable
            or form.mode not in {
                "qr",
                "gps",
                "gps_photo",
                "password",
            }
        ):
            return self._checkin_view(
                "waiting_parameter",
                "无法识别该签到项的提交方式",
            )

        parameters = CheckinParameters(
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            accuracy=payload.get("accuracy"),
            password=str(payload.get("password") or ""),
        )

        submit_started = False

        def mark_submitting():
            nonlocal submit_started
            if not submit_started and before_submit is not None:
                before_submit()
                submit_started = True

        try:
            fields = build_submission_fields(
                form,
                parameters,
                remote_item_id=str(item["remote_item_id"]),
            )
        except ClassCubeValidationError as exc:
            return self._checkin_view(
                "waiting_parameter",
                str(exc),
            )

        try:
            mark_submitting()
            result = self.client.submit_form(
                account["cookie"],
                form,
                fields,
            )
        except ClassCubeCookieExpired:
            self._mark_account_expired(
                account["id"],
                actor_user_id,
                is_admin,
            )
            return self._checkin_view(
                "failed",
                "班级魔方登录已失效，请重新扫码",
            )
        except ClassCubeSubmissionUnknown as exc:
            if self._confirm_unknown_submission(context, actor):
                return self._checkin_view(
                    "success",
                    "签到成功",
                )
            self._log_remote_failure("提交签到", exc)
            return self._checkin_view(
                "unknown_result",
                "签到请求已发送，但暂时无法确认结果",
            )
        except (ClassCubeRequestError, OSError) as exc:
            self._log_remote_failure("提交签到", exc)
            return self._checkin_view(
                "failed",
                "班级魔方签到失败，请稍后重试",
            )

        if result.status == "cookie_expired":
            self._mark_account_expired(
                account["id"],
                actor_user_id,
                is_admin,
            )
            return self._checkin_view(
                "failed",
                "班级魔方登录已失效，请重新扫码",
            )
        if result.status == "success":
            return self._checkin_view("success", "签到成功")
        if result.status == "already_signed":
            return self._checkin_view(
                "already_signed",
                "该签到项已经完成",
            )
        if result.status == "password_error":
            return self._checkin_view(
                "failed",
                "签到密码错误",
            )
        if result.status == "unknown_result":
            if self._confirm_unknown_submission(context, actor):
                return self._checkin_view(
                    "success",
                    "签到成功",
                )
            return self._checkin_view(
                "unknown_result",
                "签到请求已发送，但暂时无法确认结果",
            )
        if result.status == "not_started":
            return self._checkin_view(
                "failed",
                "签到尚未开始",
            )
        return self._checkin_view(
            "failed",
            "班级魔方签到失败",
        )

    @staticmethod
    def _owned_photo_path(
        relative_path: str,
        owner_user_id: int,
    ) -> Path:
        normalized = str(relative_path)
        if (
            not normalized
            or "\x00" in normalized
            or "\\" in normalized
            or normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
        ):
            raise ClassCubeValidationError(
                "签到照片路径无效"
            )
        relative = PurePosixPath(normalized)
        parts = relative.parts
        if (
            len(parts) != 3
            or ".." in parts
            or "." in parts
            or parts[0] != "class-cube"
            or parts[1] != str(owner_user_id)
        ):
            raise ClassCubeValidationError(
                "签到照片不属于当前账号"
            )

        class_cube_root = config.CLASS_CUBE_UPLOAD_DIR
        owner_root = class_cube_root / str(owner_user_id)
        candidate = owner_root / parts[2]
        _reject_symlink_components(
            class_cube_root,
            owner_root,
            candidate,
        )
        try:
            resolved = candidate.resolve(strict=True)
            resolved_owner_root = owner_root.resolve(strict=True)
            resolved_class_cube_root = (
                class_cube_root.resolve(strict=True)
            )
            resolved_upload_root = config.UPLOAD_DIR.resolve(
                strict=True
            )
        except (OSError, ValueError) as exc:
            raise ClassCubeValidationError(
                "签到照片不存在"
            ) from exc
        if (
            not _path_is_contained(
                resolved_class_cube_root,
                resolved_upload_root,
            )
            or not _path_is_contained(
                resolved_owner_root,
                resolved_class_cube_root,
            )
            or not _path_is_contained(
                resolved,
                resolved_owner_root,
            )
            or not resolved.is_file()
        ):
            raise ClassCubeValidationError(
                "签到照片不属于当前账号"
            )

        extension = resolved.suffix.lower()
        if extension not in _PHOTO_CONTENT_TYPES:
            raise ClassCubeValidationError(
                "签到照片格式无效"
            )
        try:
            with resolved.open("rb") as photo_file:
                header = photo_file.read(16)
        except OSError as exc:
            raise ClassCubeValidationError(
                "无法读取签到照片"
            ) from exc
        if not _photo_signature(extension, header):
            raise ClassCubeValidationError(
                "签到照片内容无效"
            )
        return resolved

    def save_photo(
        self,
        upload: UploadFile,
        actor: dict[str, Any],
        account_id: int | None = None,
    ) -> dict[str, str]:
        actor_user_id, is_admin = self._actor_scope(actor)
        owner_user_id = actor_user_id
        if account_id is not None:
            account = self.repository.get_account(
                account_id,
                actor_user_id,
                is_admin,
            )
            owner_user_id = int(account["owner_user_id"])

        extension = Path(upload.filename or "").suffix.lower()
        expected_type = _PHOTO_CONTENT_TYPES.get(extension)
        content_type = str(upload.content_type or "").lower()
        if expected_type is None or content_type != expected_type:
            raise ClassCubeValidationError(
                "仅支持 JPEG、PNG、WEBP 图片"
            )
        normalized_extension = (
            ".jpg" if extension == ".jpeg" else extension
        )

        first_chunk = upload.file.read(
            CLASS_CUBE_PHOTO_CHUNK_BYTES
        )
        if not _photo_signature(extension, first_chunk[:16]):
            raise ClassCubeValidationError(
                "图片内容与声明格式不一致"
            )

        owner_directory = (
            config.CLASS_CUBE_UPLOAD_DIR
            / str(owner_user_id)
        )
        class_cube_root = config.CLASS_CUBE_UPLOAD_DIR
        target = None
        written = 0
        try:
            _reject_symlink_components(
                class_cube_root,
                owner_directory,
            )
            owner_directory.mkdir(
                parents=True,
                exist_ok=True,
            )
            _reject_symlink_components(
                class_cube_root,
                owner_directory,
            )
            resolved_upload_root = config.UPLOAD_DIR.resolve(
                strict=True
            )
            resolved_class_cube_root = class_cube_root.resolve(
                strict=True
            )
            resolved_owner_directory = owner_directory.resolve(
                strict=True
            )
            if (
                not _path_is_contained(
                    resolved_class_cube_root,
                    resolved_upload_root,
                )
                or not _path_is_contained(
                    resolved_owner_directory,
                    resolved_class_cube_root,
                )
            ):
                raise ClassCubeValidationError(
                    "签到照片存储路径无效"
                )
            target = owner_directory / (
                f"{uuid.uuid4().hex}{normalized_extension}"
            )
            _reject_symlink_components(target)
            if not _path_is_contained(
                target.resolve(strict=False),
                resolved_owner_directory,
            ):
                raise ClassCubeValidationError(
                    "签到照片存储路径无效"
                )
            with target.open("xb") as output:
                chunk = first_chunk
                while chunk:
                    written += len(chunk)
                    if written > CLASS_CUBE_PHOTO_MAX_BYTES:
                        raise ClassCubeValidationError(
                            "签到照片不能超过 10MB"
                        )
                    output.write(chunk)
                    chunk = upload.file.read(
                        CLASS_CUBE_PHOTO_CHUNK_BYTES
                    )
        except Exception:
            try:
                if target is not None:
                    target.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        relative = (
            PurePosixPath("class-cube")
            / str(owner_user_id)
            / target.name
        ).as_posix()
        return {
            "path": relative,
            "url": f"/uploads/{relative}",
        }
