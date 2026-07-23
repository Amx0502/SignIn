import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .auth_database import AuthDatabase
from .auth_models import UserRow, UserSessionRow


PBKDF2_ITERATIONS = 600_000


class DuplicateUsernameError(ValueError):
    pass


class LastAdminError(ValueError):
    pass


class UserNotFoundError(IndexError):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> tuple[bool, bool]:
    if encoded.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_hex, digest_hex = encoded.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
            return hmac.compare_digest(candidate.hex(), digest_hex), False
        except (ValueError, TypeError):
            return False, False
    try:
        digest, salt = encoded.split(":", 1)
    except ValueError:
        return False, False
    candidate = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    valid = hmac.compare_digest(candidate, digest)
    return valid, valid


class AuthRepository:
    def __init__(self, database: AuthDatabase):
        self.database = database

    @staticmethod
    def _to_dict(row: UserRow) -> dict:
        return {
            "id": row.id,
            "username": row.username,
            "role": row.role,
            "is_active": row.is_active,
            "must_change_password": row.must_change_password,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "last_login": row.last_login.isoformat() if row.last_login else None,
        }

    def initialize_users(self, path: Path) -> int:
        with self.database.session() as session:
            if session.scalar(select(func.count(UserRow.id))):
                return 0
            imported = 0
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("users.json 必须是对象")
                for username, item in data.items():
                    if not isinstance(item, dict):
                        raise ValueError("users.json 中的用户必须是对象")
                    session.add(UserRow(
                        username=str(item.get("username") or username),
                        password_hash=str(item.get("password_hash", "")),
                        role="admin",
                        is_active=bool(item.get("is_active", True)),
                        must_change_password=False,
                    ))
                    imported += 1
            if not imported:
                session.add(UserRow(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                    must_change_password=True,
                ))
                imported = 1
            session.flush()
            return imported

    def list_users(self) -> list[dict]:
        with self.database.session() as session:
            return [self._to_dict(row) for row in session.scalars(
                select(UserRow).order_by(UserRow.id)
            ).all()]

    def find_by_username(self, username: str) -> UserRow | None:
        with self.database.session() as session:
            return session.scalar(select(UserRow).where(UserRow.username == username))

    def get_user(self, user_id: int) -> UserRow:
        with self.database.session() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                raise UserNotFoundError(user_id)
            return row

    @staticmethod
    def _duplicate(exc: IntegrityError) -> bool:
        return bool(getattr(exc.orig, "args", ()) and exc.orig.args[0] == 1062)

    def create_user(self, username: str, password: str, role: str, is_active: bool) -> dict:
        if role not in {"admin", "user"}:
            raise ValueError("角色无效")
        try:
            with self.database.session() as session:
                row = UserRow(
                    username=username.strip(), password_hash=hash_password(password),
                    role=role, is_active=is_active, must_change_password=True,
                )
                session.add(row)
                session.flush()
                return self._to_dict(row)
        except IntegrityError as exc:
            if self._duplicate(exc):
                raise DuplicateUsernameError("用户名已存在") from exc
            raise

    def _active_admin_count(self, session) -> int:
        return int(session.scalar(select(func.count(UserRow.id)).where(
            UserRow.role == "admin", UserRow.is_active.is_(True)
        )) or 0)

    def update_user(self, user_id: int, username: str, role: str, is_active: bool) -> dict:
        if role not in {"admin", "user"}:
            raise ValueError("角色无效")
        try:
            with self.database.session() as session:
                row = session.get(UserRow, user_id)
                if row is None:
                    raise UserNotFoundError(user_id)
                if row.role == "admin" and row.is_active and (
                    role != "admin" or not is_active
                ) and self._active_admin_count(session) <= 1:
                    raise LastAdminError("必须保留至少一个启用中的管理员")
                row.username = username.strip()
                row.role = role
                row.is_active = is_active
                if not is_active:
                    session.execute(delete(UserSessionRow).where(UserSessionRow.user_id == row.id))
                session.flush()
                return self._to_dict(row)
        except IntegrityError as exc:
            if self._duplicate(exc):
                raise DuplicateUsernameError("用户名已存在") from exc
            raise

    def reset_password(self, user_id: int, new_password: str, keep_token_hash: str | None = None) -> None:
        with self.database.session() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                raise UserNotFoundError(user_id)
            row.password_hash = hash_password(new_password)
            row.must_change_password = True
            statement = delete(UserSessionRow).where(UserSessionRow.user_id == user_id)
            if keep_token_hash:
                statement = statement.where(UserSessionRow.token_hash != keep_token_hash)
            session.execute(statement)

    def delete_user(self, user_id: int, actor_user_id: int) -> None:
        if user_id == actor_user_id:
            raise ValueError("不能删除当前登录用户")
        with self.database.session() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                raise UserNotFoundError(user_id)
            if row.role == "admin" and row.is_active and self._active_admin_count(session) <= 1:
                raise LastAdminError("必须保留至少一个启用中的管理员")
            session.delete(row)

    def authenticate(self, username: str, password: str) -> UserRow | None:
        with self.database.session() as session:
            row = session.scalar(select(UserRow).where(UserRow.username == username))
            if row is None or not row.is_active:
                return None
            valid, upgrade = verify_password(password, row.password_hash)
            if not valid:
                return None
            if upgrade:
                row.password_hash = hash_password(password)
            row.last_login = datetime.now()
            session.flush()
            return row

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        keep_token_hash: str,
    ) -> bool:
        with self.database.session() as session:
            row = session.get(UserRow, user_id)
            if row is None or not verify_password(current_password, row.password_hash)[0]:
                return False
            row.password_hash = hash_password(new_password)
            row.must_change_password = False
            session.execute(
                delete(UserSessionRow).where(
                    UserSessionRow.user_id == user_id,
                    UserSessionRow.token_hash != keep_token_hash,
                )
            )
            return True

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_session(self, user_id: int, ip_address: str, expires_seconds: int) -> tuple[str, datetime]:
        token = secrets.token_hex(32)
        expires_at = datetime.now() + timedelta(seconds=expires_seconds)
        with self.database.session() as session:
            session.add(UserSessionRow(
                user_id=user_id, token_hash=self.token_hash(token),
                ip_address=ip_address, expires_at=expires_at,
            ))
        return token, expires_at

    def verify_session(self, token: str) -> dict | None:
        token_hash = self.token_hash(token)
        with self.database.session() as session:
            row = session.scalar(
                select(UserSessionRow)
                .options(joinedload(UserSessionRow.user))
                .where(UserSessionRow.token_hash == token_hash)
            )
            if row is None:
                return None
            if row.expires_at <= datetime.now() or not row.user.is_active:
                session.delete(row)
                return None
            return self._to_dict(row.user)

    def logout(self, token: str) -> None:
        with self.database.session() as session:
            session.execute(delete(UserSessionRow).where(
                UserSessionRow.token_hash == self.token_hash(token)
            ))

    def has_raw_token(self, token: str) -> bool:
        with self.database.session() as session:
            return bool(session.scalar(select(func.count(UserSessionRow.id)).where(
                UserSessionRow.token_hash == token
            )))
