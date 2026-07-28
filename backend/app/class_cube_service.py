from dataclasses import dataclass
from threading import RLock
from typing import Any

from .class_cube_client import (
    ClassCubeClient,
    ClassCubeCookieExpired,
    ClassCubeRequestError,
    QrSessionNotFound,
)
from .class_cube_models import (
    account_view,
    course_view,
    item_view,
    qr_result_view,
)
from .class_cube_repository import (
    ClassCubeNotFound,
    ClassCubeRepository,
)


class ClassCubeValidationError(ValueError):
    pass


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


class ClassCubeService:
    def __init__(
        self,
        repository: ClassCubeRepository,
        client: ClassCubeClient,
        logger,
    ):
        self.repository = repository
        self.client = client
        self.logger = logger
        self._qr_targets: dict[str, _QrTarget] = {}
        self._qr_lock = RLock()

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
        with self._qr_lock:
            self._qr_targets[created.token] = _QrTarget(
                owner_user_id=actor_user_id,
                account_id=account_id,
            )
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
        self.repository.delete_account(
            account_id,
            actor_user_id,
            is_admin,
        )
        return True

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
