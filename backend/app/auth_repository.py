import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from .auth_database import AuthDatabase
from .auth_models import UserFeaturePolicyRow, UserRow, UserSessionRow
from .password_vault import decrypt_password, encrypt_password
from .membership_constants import (
    CARD_MONTHLY,
    CARD_SINGLE,
    CARD_TYPES,
    DEFAULT_CARD_DELETE_DELAY_SECONDS,
    DEFAULT_CARD_TOTAL_USES,
    MAX_CARD_DELETE_DELAY_SECONDS,
    MAX_CARD_TOTAL_USES,
    MIN_CARD_DELETE_DELAY_SECONDS,
    MIN_CARD_TOTAL_USES,
    MONTHLY_CARD_DAYS,
    PLATFORM_SCOPES,
)


PBKDF2_ITERATIONS = 600_000


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


MAX_REMARK_LENGTH = 255


def normalize_remark(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized[:MAX_REMARK_LENGTH]


def normalize_delete_delay_seconds(value: int | None) -> int:
    if value is None:
        return DEFAULT_CARD_DELETE_DELAY_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("次卡删除延迟必须是整数秒") from exc
    if not MIN_CARD_DELETE_DELAY_SECONDS <= seconds <= MAX_CARD_DELETE_DELAY_SECONDS:
        raise ValueError(
            "次卡删除延迟必须在 "
            f"{MIN_CARD_DELETE_DELAY_SECONDS} 到 "
            f"{MAX_CARD_DELETE_DELAY_SECONDS} 秒之间"
        )
    return seconds


def normalize_total_uses(value: int | None) -> int:
    if value is None:
        return DEFAULT_CARD_TOTAL_USES
    try:
        total = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("次卡签到次数必须是整数") from exc
    if not MIN_CARD_TOTAL_USES <= total <= MAX_CARD_TOTAL_USES:
        raise ValueError(
            "次卡签到次数必须在 "
            f"{MIN_CARD_TOTAL_USES} 到 {MAX_CARD_TOTAL_USES} 之间"
        )
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
            else DEFAULT_CARD_TOTAL_USES
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
        archived_at = (
            row.card_delete_due_at or row.expires_at
            if row.expires_at and row.expires_at <= now
            else None
        )
        return {
            "id": row.id,
            "username": row.username,
            "role": row.role,
            "is_active": row.is_active,
            "platform_scope": row.platform_scope or "all",
            "remark": row.remark,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "last_login": row.last_login.isoformat() if row.last_login else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "is_expired": bool(
                row.expires_at and row.expires_at <= now
            ),
            "archived_at": archived_at.isoformat() if archived_at else None,
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
                else DEFAULT_CARD_DELETE_DELAY_SECONDS
            ),
            "card_delete_due_at": (
                row.card_delete_due_at.isoformat()
                if row.card_delete_due_at
                else None
            ),
            "card_status": AuthRepository._card_status(row, now),
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
        current = now or datetime.now()
        if row.expires_at is not None and row.expires_at <= current:
            return "expired"
        if row.card_used_at is not None:
            return "used"
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

    def query_users(
        self,
        *,
        view: str = "current",
        keyword: str | None = None,
        role: str | None = None,
        card_type: str | None = None,
        platform_scope: str | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_view = str(view or "current").strip().lower()
        if normalized_view not in {"current", "archived"}:
            raise ValueError("用户视图无效")
        normalized_role = str(role or "").strip().lower() or None
        if normalized_role is not None and normalized_role not in {"admin", "user"}:
            raise ValueError("角色筛选无效")
        normalized_card = str(card_type or "").strip().lower() or None
        if normalized_card is not None and normalized_card not in {
            "none",
            CARD_SINGLE,
            CARD_MONTHLY,
        }:
            raise ValueError("会员卡筛选无效")
        normalized_scope = (
            normalize_platform_scope(platform_scope)
            if platform_scope
            else None
        )
        normalized_status = str(status or "").strip().lower() or None
        allowed_statuses = {"active", "pending", "used", "expired", "disabled"}
        if normalized_status is not None and normalized_status not in allowed_statuses:
            raise ValueError("状态筛选无效")
        current_page = max(int(page), 1)
        current_page_size = min(max(int(page_size), 1), 500)

        now = datetime.now()
        expired = and_(
            UserRow.expires_at.is_not(None),
            UserRow.expires_at <= now,
        )
        current = or_(
            UserRow.expires_at.is_(None),
            UserRow.expires_at > now,
        )
        conditions = [expired if normalized_view == "archived" else current]

        if keyword and keyword.strip():
            conditions.append(
                UserRow.username.contains(keyword.strip(), autoescape=True)
            )
        if normalized_role:
            conditions.append(UserRow.role == normalized_role)
        if normalized_card == "none":
            conditions.append(UserRow.card_type.is_(None))
        elif normalized_card:
            conditions.append(UserRow.card_type == normalized_card)
        if normalized_scope:
            conditions.append(UserRow.platform_scope == normalized_scope)
        if start_date:
            conditions.append(
                UserRow.expires_at >= datetime.combine(start_date, time.min)
            )
        if end_date:
            conditions.append(
                UserRow.expires_at < datetime.combine(
                    end_date + timedelta(days=1), time.min
                )
            )
        if normalized_status:
            status_conditions = {
                "expired": expired,
                "disabled": and_(
                    UserRow.is_active.is_(False),
                    current,
                ),
                "pending": and_(
                    UserRow.is_active.is_(True),
                    UserRow.card_type == CARD_MONTHLY,
                    UserRow.card_activated_at.is_(None),
                ),
                "used": and_(
                    UserRow.is_active.is_(True),
                    UserRow.card_type == CARD_SINGLE,
                    UserRow.card_used_at.is_not(None),
                ),
                "active": and_(
                    UserRow.is_active.is_(True),
                    or_(
                        UserRow.card_type.is_(None),
                        and_(
                            UserRow.card_type == CARD_MONTHLY,
                            UserRow.card_activated_at.is_not(None),
                        ),
                        and_(
                            UserRow.card_type == CARD_SINGLE,
                            UserRow.card_used_at.is_(None),
                        ),
                    ),
                ),
            }
            conditions.append(status_conditions[normalized_status])

        with self.database.session() as session:
            self._expire_due_users(session, now)
            total = int(session.scalar(
                select(func.count(UserRow.id)).where(*conditions)
            ) or 0)
            current_total = int(session.scalar(
                select(func.count(UserRow.id)).where(current)
            ) or 0)
            archived_total = int(session.scalar(
                select(func.count(UserRow.id)).where(expired)
            ) or 0)
            order_by = (
                (UserRow.expires_at.desc(), UserRow.id.desc())
                if normalized_view == "archived"
                else (UserRow.id.desc(),)
            )
            rows = session.scalars(
                select(UserRow)
                .options(selectinload(UserRow.feature_policy))
                .where(*conditions)
                .order_by(*order_by)
                .offset((current_page - 1) * current_page_size)
                .limit(current_page_size)
            ).all()
            return {
                "items": [self._to_dict(row) for row in rows],
                "total": total,
                "page": current_page,
                "page_size": current_page_size,
                "current_total": current_total,
                "archived_total": archived_total,
            }

    def export_archived_users(
        self,
        *,
        keyword: str | None = None,
        card_type: str | None = None,
        platform_scope: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while True:
            result = self.query_users(
                view="archived",
                keyword=keyword,
                card_type=card_type,
                platform_scope=platform_scope,
                start_date=start_date,
                end_date=end_date,
                page=page,
                page_size=500,
            )
            rows.extend(result["items"])
            if not result["items"] or len(rows) >= result["total"]:
                return rows
            page += 1

    def export_current_users(
        self,
        *,
        keyword: str | None = None,
        card_type: str | None = None,
        platform_scope: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Collect all current users matching the filters, with the decrypted
        admin-set password copy when available."""
        items: list[dict] = []
        page = 1
        while True:
            result = self.query_users(
                view="current",
                keyword=keyword,
                card_type=card_type,
                platform_scope=platform_scope,
                status=status,
                page=page,
                page_size=500,
            )
            items.extend(result["items"])
            if not result["items"] or len(items) >= result["total"]:
                break
            page += 1

        user_ids = [item["id"] for item in items]
        encrypted: dict[int, bytes | None] = {}
        if user_ids:
            with self.database.session() as session:
                rows = session.execute(
                    select(UserRow.id, UserRow.initial_password_enc).where(
                        UserRow.id.in_(user_ids)
                    )
                ).all()
                for row_id, blob in rows:
                    encrypted[row_id] = blob
        for item in items:
            item["export_password"] = decrypt_password(
                encrypted.get(item["id"])
            )
        return items

    def get_user_credentials(self, user_id: int) -> dict:
        """Return one user's basic info with the decrypted admin-set
        password copy when available."""
        with self.database.session() as session:
            row = session.get(UserRow, int(user_id))
            if row is None:
                raise UserNotFoundError(user_id)
            blob = row.initial_password_enc
            info = self._to_dict(row)
        info["initial_password"] = decrypt_password(blob)
        return info

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
        class_cube_account_limit: int | None = None,
        xxqd_account_limit: int | None = None,
        location_search_daily_limit: int | None = None,
        expires_at: datetime | None = None,
        card_type: str | None = None,
        card_delete_delay_seconds: int | None = None,
        card_total_uses: int | None = None,
        remark: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        expires_at = normalize_expiration(expires_at)
        card_type = normalize_card_type(card_type)
        remark = normalize_remark(remark)
        created_by = (str(created_by).strip() or None) if created_by else None
        delete_delay_seconds = normalize_delete_delay_seconds(
            card_delete_delay_seconds
        )
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
                    card_delete_delay_seconds=delete_delay_seconds,
                    card_total_uses=total_uses,
                    initial_password_enc=encrypt_password(password),
                    remark=remark,
                    created_by=created_by,
                )
                session.add(row)
                session.flush()
                policy = UserFeaturePolicyRow(
                    user_id=row.id,
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
        class_cube_account_limit: int | None = None,
        xxqd_account_limit: int | None = None,
        location_search_daily_limit: int | None = None,
        expires_at: datetime | None = None,
        card_type: str | None = None,
        card_delete_delay_seconds: int | None = None,
        card_total_uses: int | None = None,
        remark: str | None = None,
    ) -> dict:
        expires_at = normalize_expiration(expires_at)
        card_type = normalize_card_type(card_type)
        remark = normalize_remark(remark)
        delete_delay_seconds = (
            normalize_delete_delay_seconds(card_delete_delay_seconds)
            if card_delete_delay_seconds is not None
            else None
        )
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
                row.remark = remark
                if role != "user" or card_type is None:
                    row.expires_at = expires_at if role == "user" else None
                    row.card_type = None
                    row.card_activated_at = None
                    row.card_used_at = None
                    row.card_used_count = 0
                    row.card_total_uses = DEFAULT_CARD_TOTAL_USES
                    row.card_delete_delay_seconds = (
                        DEFAULT_CARD_DELETE_DELAY_SECONDS
                    )
                    row.card_delete_due_at = None
                else:
                    row.card_type = card_type
                    if previous_card_type != card_type:
                        row.card_activated_at = None
                        row.card_used_at = None
                        row.card_used_count = 0
                        row.card_total_uses = (
                            total_uses or DEFAULT_CARD_TOTAL_USES
                        )
                        row.expires_at = None
                        row.card_delete_due_at = None
                        row.card_delete_delay_seconds = (
                            delete_delay_seconds
                            if delete_delay_seconds is not None
                            else DEFAULT_CARD_DELETE_DELAY_SECONDS
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
                        row.card_delete_due_at = row.expires_at
                    elif card_type == CARD_SINGLE:
                        row.expires_at = None
                    if (
                        card_type == CARD_SINGLE
                        and delete_delay_seconds is not None
                    ):
                        row.card_delete_delay_seconds = delete_delay_seconds
                        if row.card_used_at is not None:
                            row.expires_at = (
                                row.card_used_at
                                + timedelta(seconds=delete_delay_seconds)
                            )
                            row.card_delete_due_at = row.expires_at
                    if card_type == CARD_SINGLE and total_uses is not None:
                        if total_uses < int(row.card_used_count or 0):
                            raise ValueError(
                                "次卡总次数不能小于已签到次数"
                            )
                        current_total_uses = normalize_total_uses(
                            row.card_total_uses
                        )
                        if (
                            row.card_used_at is not None
                            and total_uses != current_total_uses
                        ):
                            raise ValueError("已核销次卡不能修改签到次数")
                        row.card_total_uses = total_uses
                        if (
                            row.card_used_at is None
                            and row.card_used_count
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
            row.initial_password_enc = encrypt_password(new_password)
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
                row.card_delete_due_at = row.expires_at
            session.flush()
            return row

    def user_is_expired(
        self,
        user_id: int,
        now: datetime | None = None,
    ) -> bool:
        with self.database.session() as session:
            row = session.get(UserRow, int(user_id))
            if row is None:
                raise UserNotFoundError(user_id)
            current = now or datetime.now()
            if row.card_type:
                return AuthRepository._card_status(row, current) == "expired"
            return bool(
                row.expires_at is not None
                and row.expires_at <= current
            )

    def record_single_card_checkin(self, user_id: int) -> dict | None:
        with self.database.session() as session:
            row = session.scalar(
                select(UserRow)
                .where(UserRow.id == int(user_id))
                .with_for_update()
            )
            now = datetime.now()
            if (
                row is None
                or row.role != "user"
                or not row.is_active
                or (
                    row.expires_at is not None
                    and row.expires_at <= now
                )
                or row.card_type != CARD_SINGLE
                or row.card_used_at is not None
            ):
                return None
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

    def list_due_card_cleanup_user_ids(
        self,
        now: datetime | None = None,
    ) -> list[int]:
        """Return cards whose platform data is due for cleanup.

        ``expires_at`` controls account access. ``card_delete_due_at`` is the
        separate cleanup schedule used to remove platform accounts and tasks
        while preserving the system user and run history.
        """
        current = now or datetime.now()
        with self.database.session() as session:
            return list(session.scalars(
                select(UserRow.id).where(
                    UserRow.role == "user",
                    UserRow.card_type.in_(CARD_TYPES),
                    UserRow.card_delete_due_at.is_not(None),
                    UserRow.card_delete_due_at <= current,
                )
            ).all())

    def expire_due_memberships(self) -> int:
        with self.database.session() as session:
            return self._expire_due_users(session)

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
            # User changed their own password: the admin-side copy is no
            # longer valid, drop it so exports show "未保存".
            row.initial_password_enc = None
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
