import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from .auth_database import AuthDatabase
from .auth_models import UserFeaturePolicyRow, UserRow, UserSessionRow


PBKDF2_ITERATIONS = 600_000
CARD_SINGLE = "single"
CARD_MONTHLY = "monthly"
CARD_TYPES = {CARD_SINGLE, CARD_MONTHLY}
MONTHLY_CARD_DAYS = 30
PLATFORM_SCOPES = {"all", "xxqd", "class_cube"}


class DuplicateUsernameError(ValueError):
    pass


class LastAdminError(ValueError):
    pass


class UserNotFoundError(IndexError):
    pass


def normalize_expiration(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def normalize_card_type(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in CARD_TYPES:
        raise ValueError("会员卡类型无效")
    return normalized


def normalize_platform_scope(value: str | None) -> str:
    normalized = str(value or "all").strip().lower()
    if normalized not in PLATFORM_SCOPES:
        raise ValueError("用户平台范围无效")
    return normalized


def normalize_delete_delay_minutes(value: int | None) -> int:
    if value is None:
        return 5
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("次卡删除延迟必须是整数分钟") from exc
    if not 0 <= minutes <= 1440:
        raise ValueError("次卡删除延迟必须在 0 到 1440 分钟之间")
    return minutes


def normalize_delete_delay_seconds(value: int | None) -> int:
    if value is None:
        return 30
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("次卡删除延迟必须是整数秒") from exc
    if not 0 <= seconds <= 86400:
        raise ValueError("次卡删除延迟必须在 0 到 86400 秒之间")
    return seconds


def normalize_total_uses(value: int | None) -> int:
    if value is None:
        return 1
    try:
        total = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("次卡签到次数必须是整数") from exc
    if not 1 <= total <= 999:
        raise ValueError("次卡签到次数必须在 1 到 999 之间")
    return total


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
        policy = row.feature_policy
        now = datetime.now()
        total_uses = int(
            row.card_total_uses
            if row.card_total_uses is not None
            else 1
        )
        used_count = int(
            row.card_used_count
            if row.card_used_count is not None
            else 0
        )
        location_search_used = (
            int(policy.location_search_used or 0)
            if policy and policy.location_search_date == date.today()
            else 0
        )
        return {
            "id": row.id,
            "username": row.username,
            "role": row.role,
            "is_active": row.is_active,
            "platform_scope": row.platform_scope or "all",
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "last_login": row.last_login.isoformat() if row.last_login else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "is_expired": bool(
                row.expires_at and row.expires_at <= now
            ),
            "card_type": row.card_type,
            "card_activated_at": (
                row.card_activated_at.isoformat()
                if row.card_activated_at
                else None
            ),
            "card_used_at": (
                row.card_used_at.isoformat()
                if row.card_used_at
                else None
            ),
            "card_total_uses": total_uses,
            "card_used_count": used_count,
            "card_remaining_uses": max(total_uses - used_count, 0),
            "card_delete_delay_seconds": int(
                row.card_delete_delay_seconds
                if row.card_delete_delay_seconds is not None
                else 30
            ),
            "card_delete_delay_minutes": int(
                row.card_delete_delay_seconds
                if row.card_delete_delay_seconds is not None
                else 30
            ) // 60,
            "card_delete_due_at": (
                row.card_delete_due_at.isoformat()
                if row.card_delete_due_at
                else None
            ),
            "card_status": AuthRepository._card_status(row, now),
            "class_cube_only": bool(policy.class_cube_only) if policy else False,
            "class_cube_account_limit": (
                policy.class_cube_account_limit if policy else None
            ),
            "xxqd_account_limit": (
                policy.xxqd_account_limit if policy else None
            ),
            "location_search_daily_limit": (
                policy.location_search_daily_limit if policy else None
            ),
            "location_search_used": location_search_used,
            "location_search_remaining": (
                max(
                    int(policy.location_search_daily_limit)
                    - location_search_used,
                    0,
                )
                if policy
                and policy.location_search_daily_limit is not None
                else None
            ),
        }

    @staticmethod
    def _card_status(row: UserRow, now: datetime | None = None) -> str | None:
        if not row.card_type:
            return None
        if row.card_used_at is not None:
            return "used"
        if not row.is_active:
            return "expired"
        current = now or datetime.now()
        if row.expires_at is not None and row.expires_at <= current:
            return "expired"
        if row.card_type == CARD_MONTHLY and row.card_activated_at is None:
            return "pending"
        return "active"

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
                    ))
                    imported += 1
            if not imported:
                session.add(UserRow(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                ))
                imported = 1
            session.flush()
            return imported

    def list_users(self) -> list[dict]:
        with self.database.session() as session:
            self._expire_due_users(session)
            return [self._to_dict(row) for row in session.scalars(
                select(UserRow)
                .options(selectinload(UserRow.feature_policy))
                .order_by(UserRow.id)
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

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        is_active: bool,
        *,
        platform_scope: str = "all",
        class_cube_only: bool = False,
        class_cube_account_limit: int | None = None,
        xxqd_account_limit: int | None = None,
        location_search_daily_limit: int | None = None,
        expires_at: datetime | None = None,
        card_type: str | None = None,
        card_delete_delay_minutes: int | None = None,
        card_delete_delay_seconds: int | None = None,
        card_total_uses: int | None = None,
    ) -> dict:
        expires_at = normalize_expiration(expires_at)
        card_type = normalize_card_type(card_type)
        if card_delete_delay_seconds is not None:
            delete_delay_seconds = normalize_delete_delay_seconds(
                card_delete_delay_seconds
            )
        elif card_delete_delay_minutes is not None:
            delete_delay_seconds = (
                normalize_delete_delay_minutes(card_delete_delay_minutes) * 60
            )
        else:
            delete_delay_seconds = 30
        total_uses = normalize_total_uses(card_total_uses)
        platform_scope = normalize_platform_scope(platform_scope)
        if role not in {"admin", "user"}:
            raise ValueError("角色无效")
        if card_type is not None and role != "user":
            raise ValueError("只有普通用户可以分配会员卡")
        if role != "user":
            platform_scope = "all"
        if card_type is not None and platform_scope == "all":
            raise ValueError("会员卡用户必须指定使用平台")
        if role == "admin" and expires_at is not None:
            raise ValueError("管理员账号不能设置到期时间")
        if card_type is not None:
            expires_at = None
        if is_active and expires_at is not None and expires_at <= datetime.now():
            raise ValueError("启用用户的到期时间必须晚于当前时间")
        try:
            with self.database.session() as session:
                row = UserRow(
                    username=username.strip(), password_hash=hash_password(password),
                    role=role, is_active=is_active, expires_at=expires_at,
                    platform_scope=platform_scope,
                    card_type=card_type,
                    card_delete_delay_minutes=delete_delay_seconds // 60,
                    card_delete_delay_seconds=delete_delay_seconds,
                    card_total_uses=total_uses,
                )
                session.add(row)
                session.flush()
                policy = UserFeaturePolicyRow(
                    user_id=row.id,
                    class_cube_only=bool(class_cube_only and role == "user"),
                    class_cube_account_limit=(
                        class_cube_account_limit if role == "user" else None
                    ),
                    xxqd_account_limit=(
                        xxqd_account_limit if role == "user" else None
                    ),
                    location_search_daily_limit=(
                        location_search_daily_limit
                        if role == "user"
                        else None
                    ),
                )
                session.add(policy)
                row.feature_policy = policy
                return self._to_dict(row)
        except IntegrityError as exc:
            if self._duplicate(exc):
                raise DuplicateUsernameError("用户名已存在") from exc
            raise

    def _active_admin_count(self, session) -> int:
        return int(session.scalar(select(func.count(UserRow.id)).where(
            UserRow.role == "admin", UserRow.is_active.is_(True)
        )) or 0)

    def update_user(
        self,
        user_id: int,
        username: str,
        role: str,
        is_active: bool,
        *,
        platform_scope: str = "all",
        class_cube_only: bool = False,
        class_cube_account_limit: int | None = None,
        xxqd_account_limit: int | None = None,
        location_search_daily_limit: int | None = None,
        expires_at: datetime | None = None,
        card_type: str | None = None,
        card_delete_delay_minutes: int | None = None,
        card_delete_delay_seconds: int | None = None,
        card_total_uses: int | None = None,
    ) -> dict:
        expires_at = normalize_expiration(expires_at)
        card_type = normalize_card_type(card_type)
        if card_delete_delay_seconds is not None:
            delete_delay_seconds = normalize_delete_delay_seconds(
                card_delete_delay_seconds
            )
        elif card_delete_delay_minutes is not None:
            delete_delay_seconds = (
                normalize_delete_delay_minutes(card_delete_delay_minutes) * 60
            )
        else:
            delete_delay_seconds = None
        total_uses = (
            normalize_total_uses(card_total_uses)
            if card_total_uses is not None
            else None
        )
        platform_scope = normalize_platform_scope(platform_scope)
        if role not in {"admin", "user"}:
            raise ValueError("角色无效")
        if card_type is not None and role != "user":
            raise ValueError("只有普通用户可以分配会员卡")
        if role != "user":
            platform_scope = "all"
        if card_type is not None and platform_scope == "all":
            raise ValueError("会员卡用户必须指定使用平台")
        if role == "admin" and expires_at is not None:
            raise ValueError("管理员账号不能设置到期时间")
        if is_active and expires_at is not None and expires_at <= datetime.now():
            raise ValueError("启用用户的到期时间必须晚于当前时间")
        try:
            with self.database.session() as session:
                row = session.get(UserRow, user_id)
                if row is None:
                    raise UserNotFoundError(user_id)
                if row.role == "admin" and row.is_active and (
                    role != "admin" or not is_active
                ) and self._active_admin_count(session) <= 1:
                    raise LastAdminError("必须保留至少一个启用中的管理员")
                previous_card_type = row.card_type
                row.username = username.strip()
                row.role = role
                row.is_active = is_active
                row.platform_scope = platform_scope
                if role != "user" or card_type is None:
                    row.expires_at = expires_at if role == "user" else None
                    row.card_type = None
                    row.card_activated_at = None
                    row.card_used_at = None
                    row.card_used_count = 0
                    row.card_total_uses = 1
                    row.card_delete_delay_seconds = 30
                    row.card_delete_delay_minutes = 0
                    row.card_delete_due_at = None
                else:
                    row.card_type = card_type
                    if previous_card_type != card_type:
                        row.card_activated_at = None
                        row.card_used_at = None
                        row.card_used_count = 0
                        row.card_total_uses = total_uses or 1
                        row.expires_at = None
                        row.card_delete_due_at = None
                        row.card_delete_delay_seconds = (
                            delete_delay_seconds
                            if delete_delay_seconds is not None
                            else 30
                        )
                        row.card_delete_delay_minutes = (
                            row.card_delete_delay_seconds // 60
                        )
                    elif (
                        card_type == CARD_MONTHLY
                        and row.card_activated_at is not None
                        and row.expires_at is None
                    ):
                        row.expires_at = (
                            row.card_activated_at
                            + timedelta(days=MONTHLY_CARD_DAYS)
                        )
                    elif card_type == CARD_SINGLE:
                        row.expires_at = None
                    if (
                        card_type == CARD_SINGLE
                        and delete_delay_seconds is not None
                    ):
                        row.card_delete_delay_seconds = delete_delay_seconds
                        row.card_delete_delay_minutes = (
                            delete_delay_seconds // 60
                        )
                    if card_type == CARD_SINGLE and total_uses is not None:
                        if row.card_used_at is not None:
                            raise ValueError("已核销次卡不能修改签到次数")
                        if total_uses < int(row.card_used_count or 0):
                            raise ValueError(
                                "次卡总次数不能小于已签到次数"
                            )
                        row.card_total_uses = total_uses
                        if (
                            row.card_used_count
                            and row.card_used_count >= total_uses
                        ):
                            now = datetime.now()
                            row.card_used_at = now
                            delete_due_at = now + timedelta(
                                seconds=normalize_delete_delay_seconds(
                                    row.card_delete_delay_seconds
                                )
                            )
                            row.expires_at = delete_due_at
                            row.card_delete_due_at = delete_due_at
                policy = session.get(UserFeaturePolicyRow, row.id)
                if policy is None:
                    policy = UserFeaturePolicyRow(user_id=row.id)
                    session.add(policy)
                policy.class_cube_only = bool(
                    class_cube_only and role == "user"
                )
                policy.class_cube_account_limit = (
                    class_cube_account_limit if role == "user" else None
                )
                policy.xxqd_account_limit = (
                    xxqd_account_limit if role == "user" else None
                )
                policy.location_search_daily_limit = (
                    location_search_daily_limit if role == "user" else None
                )
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
            self._expire_due_users(session)
            row = session.scalar(select(UserRow).where(UserRow.username == username))
            if row is None or not row.is_active:
                return None
            valid, upgrade = verify_password(password, row.password_hash)
            if not valid:
                return None
            if upgrade:
                row.password_hash = hash_password(password)
            now = datetime.now()
            row.last_login = now
            if (
                row.card_type == CARD_MONTHLY
                and row.card_activated_at is None
            ):
                row.card_activated_at = now
                row.expires_at = now + timedelta(days=MONTHLY_CARD_DAYS)
            session.flush()
            return row

    def record_single_card_checkin(self, user_id: int) -> dict | None:
        with self.database.session() as session:
            row = session.scalar(
                select(UserRow)
                .where(UserRow.id == int(user_id))
                .with_for_update()
            )
            if (
                row is None
                or row.role != "user"
                or row.card_type != CARD_SINGLE
                or row.card_used_at is not None
            ):
                return None
            now = datetime.now()
            total_uses = normalize_total_uses(row.card_total_uses)
            used_count = min(
                int(row.card_used_count or 0) + 1,
                total_uses,
            )
            row.card_used_count = used_count
            consumed = used_count >= total_uses
            if consumed:
                delete_delay_seconds = normalize_delete_delay_seconds(
                    row.card_delete_delay_seconds
                )
                row.card_used_at = now
                delete_due_at = now + timedelta(
                    seconds=delete_delay_seconds
                )
                row.expires_at = delete_due_at
                row.card_delete_due_at = delete_due_at
            row.updated_at = now
            session.flush()
            return {
                **self._to_dict(row),
                "card_consumed": consumed,
            }

    def list_due_single_card_user_ids(
        self,
        now: datetime | None = None,
    ) -> list[int]:
        current = now or datetime.now()
        with self.database.session() as session:
            return list(session.scalars(
                select(UserRow.id).where(
                    UserRow.role == "user",
                    UserRow.card_type == CARD_SINGLE,
                    UserRow.card_used_at.is_not(None),
                    UserRow.card_delete_due_at.is_not(None),
                    UserRow.card_delete_due_at <= current,
                )
            ).all())

    def membership_is_usable(self, user_id: int) -> bool:
        with self.database.session() as session:
            row = session.get(UserRow, int(user_id))
            if row is None or not row.is_active:
                return False
            now = datetime.now()
            if row.expires_at is not None and row.expires_at <= now:
                return False
            if row.card_type == CARD_SINGLE and row.card_used_at is not None:
                return False
            return True

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
            self._expire_due_users(session)
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

    @staticmethod
    def _expire_due_users(session, now: datetime | None = None) -> int:
        current = now or datetime.now()
        user_ids = list(session.scalars(
            select(UserRow.id).where(
                UserRow.role == "user",
                UserRow.is_active.is_(True),
                UserRow.expires_at.is_not(None),
                UserRow.expires_at <= current,
            )
        ).all())
        if not user_ids:
            return 0
        session.execute(
            update(UserRow)
            .where(UserRow.id.in_(user_ids))
            .values(is_active=False, updated_at=current)
        )
        session.execute(
            delete(UserSessionRow).where(UserSessionRow.user_id.in_(user_ids))
        )
        return len(user_ids)

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
