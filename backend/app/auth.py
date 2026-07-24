import time
from typing import Optional

from .auth_repository import AuthRepository
from .models import LoginRequest


class AuthService:
    def __init__(self, repository: AuthRepository | None = None):
        self.repository = repository
        self.login_attempts: dict[str, dict] = {}

    def set_repository(self, repository: AuthRepository) -> None:
        self.repository = repository

    def _repo(self) -> AuthRepository:
        if self.repository is None:
            raise RuntimeError("认证服务尚未初始化")
        return self.repository

    def _check_login_attempts(
        self, username: str, ip_address: str
    ) -> tuple[bool, Optional[str]]:
        key = f"{username}:{ip_address}"
        now = time.time()
        attempt = self.login_attempts.setdefault(
            key, {"count": 0, "first_attempt": now, "locked_until": 0}
        )
        if attempt["locked_until"] > now:
            remaining = int(attempt["locked_until"] - now)
            return False, f"账户已锁定，请 {remaining // 60} 分 {remaining % 60} 秒后再试"
        if attempt["count"] >= 5:
            attempt["locked_until"] = now + 300
            return False, "登录失败次数过多，账户已锁定 5 分钟"
        return True, None

    def _record_login_attempt(
        self, username: str, ip_address: str, success: bool
    ) -> None:
        key = f"{username}:{ip_address}"
        now = time.time()
        attempt = self.login_attempts.setdefault(
            key, {"count": 0, "first_attempt": now, "locked_until": 0}
        )
        if success:
            self.login_attempts.pop(key, None)
        else:
            attempt["count"] += 1

    def login(self, request: LoginRequest, ip_address: str) -> tuple[bool, dict]:
        allowed, message = self._check_login_attempts(request.username, ip_address)
        if not allowed:
            return False, {"error": message}
        user = self._repo().authenticate(request.username, request.password)
        if user is None:
            self._record_login_attempt(request.username, ip_address, False)
            return False, {"error": "用户名或密码错误"}
        self._record_login_attempt(request.username, ip_address, True)
        expires_seconds = 86400 if request.remember_me else 3600
        token, expires_at = self._repo().create_session(
            user.id, ip_address, expires_seconds
        )
        return True, {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "user": self._repo().verify_session(token),
        }

    def logout(self, access_token: str) -> bool:
        self._repo().logout(access_token)
        return True

    def verify_token(self, access_token: str) -> dict | None:
        return self._repo().verify_session(access_token)

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        access_token: str,
    ) -> bool:
        return self._repo().change_password(
            user_id,
            current_password,
            new_password,
            self._repo().token_hash(access_token),
        )
