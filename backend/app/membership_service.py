import asyncio

from .auth_repository import UserNotFoundError


class MembershipService:
    def __init__(
        self,
        auth_repository,
        xxqd_repository,
        class_cube_repository,
        logger,
        *,
        cleanup_interval_seconds: int = 5,
    ) -> None:
        self.auth_repository = auth_repository
        self.xxqd_repository = xxqd_repository
        self.class_cube_repository = class_cube_repository
        self.logger = logger
        self.cleanup_interval_seconds = max(
            int(cleanup_interval_seconds), 1
        )

    def consume_checkin(self, user_id: int) -> dict | None:
        recorded = self.auth_repository.record_single_card_checkin(user_id)
        if recorded is not None and recorded.get("card_consumed"):
            self.expire_due()
        return recorded

    def is_usable(self, user_id: int) -> bool:
        return self.auth_repository.membership_is_usable(user_id)

    def expire_due(self) -> int:
        for user_id in self.auth_repository.list_due_single_card_user_ids():
            try:
                user = self.auth_repository.get_user(user_id)
                platform_scope = user.platform_scope or "all"
                if platform_scope == "xxqd":
                    self.xxqd_repository.delete_accounts_by_owner(user_id)
                elif platform_scope == "class_cube":
                    self.class_cube_repository.delete_accounts_by_owner(
                        user_id
                    )
                    self.class_cube_repository.remove_user_bindings(user_id)
            except UserNotFoundError:
                continue
            except Exception as exc:
                self.logger.warning(
                    "会员平台数据清理失败；用户：%s；异常：%s",
                    user_id,
                    type(exc).__name__,
                )
        expired_count = self.auth_repository.expire_due_memberships()
        if expired_count:
            self.logger.info(
                "已将 %s 个到期会员账号设为过期状态",
                expired_count,
            )
        return expired_count

    async def cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.expire_due)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning(
                    "会员账号定期到期检查失败；异常：%s",
                    type(exc).__name__,
                )
            await asyncio.sleep(self.cleanup_interval_seconds)
