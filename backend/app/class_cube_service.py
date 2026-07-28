from dataclasses import dataclass
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
)
from .class_cube_parser import ParsedForm
from .class_cube_repository import (
    ClassCubeNotFound,
    ClassCubeRepository,
)


class ClassCubeValidationError(ValueError):
    pass


CLASS_CUBE_PHOTO_MAX_BYTES = 10 * 1024 * 1024
CLASS_CUBE_PHOTO_CHUNK_BYTES = 64 * 1024
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
    fields: dict[str, str] = {}
    if form.item_id_field:
        fields[form.item_id_field] = str(remote_item_id)

    has_coordinate_contract = bool(
        form.latitude_field
        or form.longitude_field
        or form.accuracy_field
        or form.gps_address_field
    )
    if has_coordinate_contract:
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

    if form.password_field:
        if not parameters.password:
            raise ClassCubeValidationError("请填写签到密码")
        fields[form.password_field] = parameters.password

    if form.photo_resource_field and remote_photo_value:
        fields[form.photo_resource_field] = remote_photo_value
    return fields


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
    ):
        self.repository = repository
        self.client = client
        self.logger = logger
        self._clock = clock or time.monotonic
        self._qr_targets: dict[str, _QrTarget] = {}
        self._qr_lock = RLock()
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
            raise self._remote_error(
                "同步扫码账号资料",
                exc,
                data={
                    "account": safe_account,
                    "retryable": True,
                },
            ) from exc

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
                raise self._cookie_expired_error(exc) from exc
            except ClassCubeRequestError as exc:
                last_error = exc
                self._log_remote_failure(
                    f"同步{module}签到项",
                    exc,
                )
                continue
            self.repository.upsert_items(
                course_id,
                bundles,
                actor_user_id,
                is_admin,
            )
            successful_sources += 1

        if successful_sources == 0:
            raise ClassCubeRemoteError(
                "班级魔方签到项同步失败，请稍后重试",
                retryable=True,
            ) from last_error
        return self.list_items(course_id, actor)

    def list_items(
        self,
        course_id: int,
        actor: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actor_user_id, is_admin = self._actor_scope(actor)
        items = self.repository.list_items(
            course_id,
            actor_user_id,
            is_admin,
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

    def manual_checkin(
        self,
        item_id: int,
        payload: dict[str, Any],
        actor: dict[str, Any],
    ) -> dict[str, str]:
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

        photo_path = None
        remote_photo_value = ""
        if form.mode == "gps_photo":
            supplied_path = str(payload.get("photo_path") or "")
            if not supplied_path:
                return self._checkin_view(
                    "waiting_parameter",
                    "请上传签到照片",
                )
            try:
                owned_photo = self._owned_photo_path(
                    supplied_path,
                    int(account["owner_user_id"]),
                )
            except ClassCubeValidationError as exc:
                return self._checkin_view(
                    "waiting_parameter",
                    str(exc),
                )
            if form.file_field:
                photo_path = owned_photo
            elif (
                form.photo_resource_field
                and form.upload_action
                and form.upload_method == "post"
                and form.upload_file_field
                and form.upload_response_key
            ):
                photo_path = owned_photo
                try:
                    remote_photo_value = self.client.upload_photo(
                        account["cookie"],
                        form,
                        photo_path,
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
                except (
                    ClassCubeSubmissionUnknown,
                    ClassCubeRequestError,
                    OSError,
                ) as exc:
                    self._log_remote_failure("上传签到照片", exc)
                    return self._checkin_view(
                        "waiting_parameter",
                        "签到照片上传失败，请稍后重试",
                    )
                photo_path = None
            else:
                return self._checkin_view(
                    "waiting_parameter",
                    "无法识别远端照片上传方式",
                )

        try:
            fields = build_submission_fields(
                form,
                parameters,
                remote_item_id=str(item["remote_item_id"]),
                remote_photo_value=remote_photo_value,
            )
        except ClassCubeValidationError as exc:
            return self._checkin_view(
                "waiting_parameter",
                str(exc),
            )

        try:
            result = self.client.submit_form(
                account["cookie"],
                form,
                fields,
                photo_path=photo_path,
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
        if result.status == "unknown_result":
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
        normalized = str(relative_path).replace("\\", "/")
        if (
            not normalized
            or "\x00" in normalized
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

        candidate = config.UPLOAD_DIR.joinpath(*parts)
        if candidate.is_symlink():
            raise ClassCubeValidationError(
                "签到照片路径无效"
            )
        try:
            resolved = candidate.resolve(strict=True)
            owner_root = (
                config.CLASS_CUBE_UPLOAD_DIR
                / str(owner_user_id)
            ).resolve(strict=True)
            contained = (
                os.path.commonpath(
                    [str(resolved), str(owner_root)]
                )
                == str(owner_root)
            )
        except (OSError, ValueError) as exc:
            raise ClassCubeValidationError(
                "签到照片不存在"
            ) from exc
        if not contained or not resolved.is_file():
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
        target = owner_directory / (
            f"{uuid.uuid4().hex}{normalized_extension}"
        )
        written = 0
        try:
            owner_directory.mkdir(
                parents=True,
                exist_ok=True,
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
