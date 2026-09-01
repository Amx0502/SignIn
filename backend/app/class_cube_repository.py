from datetime import date, datetime, time, timedelta
import json
from typing import Any, Iterable
import uuid

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .class_cube_client import RemoteItemBundle
from .class_cube_database import ClassCubeDatabase
from .class_cube_db_models import (
    ClassCubeAccountBindingRow,
    ClassCubeAccountRow,
    ClassCubeCheckinItemRow,
    ClassCubeCourseRow,
    ClassCubeTaskItemClaimRow,
    ClassCubeTaskRow,
    ClassCubeTaskRunRow,
)
from .auth_models import UserFeaturePolicyRow
from .class_cube_parser import (
    PASSWORD_FIELD_ALIASES,
    ParsedCourse,
)
from .task_date_schedule import get_last_effective_occurrence


class ClassCubeNotFound(LookupError):
    pass


class ClassCubeRepository:
    DEFAULT_ACCOUNT_NAME = "班级魔方账号"

    def __init__(self, database: ClassCubeDatabase):
        self.database = database

    @staticmethod
    def _account_record(
        row: ClassCubeAccountRow,
        binding: ClassCubeAccountBindingRow | None = None,
    ) -> dict[str, Any]:
        return {
            "id": row.id,
            "owner_user_id": binding.user_id if binding else row.owner_user_id,
            "created_by_user_id": row.owner_user_id,
            "name": row.name,
            "remote_user_name": row.remote_user_name,
            "remote_uid": row.remote_uid,
            "cookie": row.cookie,
            "status": row.status,
            "last_login_at": row.last_login_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_default": bool(binding.is_default) if binding else False,
        }

    @staticmethod
    def _account_limit(session, user_id: int) -> int | None:
        policy = session.get(UserFeaturePolicyRow, user_id)
        return policy.class_cube_account_limit if policy else None

    @staticmethod
    def _binding_count(session, user_id: int) -> int:
        return int(session.scalar(
            select(func.count(ClassCubeAccountBindingRow.id)).where(
                ClassCubeAccountBindingRow.user_id == user_id
            )
        ) or 0)

    @classmethod
    def _assert_binding_capacity(cls, session, user_id: int) -> None:
        limit = cls._account_limit(session, user_id)
        if limit is not None and cls._binding_count(session, user_id) >= limit:
            raise ValueError(
                f"班级魔方账号额度已满（{limit} 个），请联系管理员调整额度"
            )

    @classmethod
    def _ensure_binding(
        cls,
        session,
        *,
        user_id: int,
        account_id: int,
        assigned_by_user_id: int | None,
    ) -> ClassCubeAccountBindingRow:
        binding = session.scalar(select(ClassCubeAccountBindingRow).where(
            ClassCubeAccountBindingRow.user_id == user_id,
            ClassCubeAccountBindingRow.account_id == account_id,
        ))
        if binding is not None:
            return binding
        cls._assert_binding_capacity(session, user_id)
        binding = ClassCubeAccountBindingRow(
            user_id=user_id,
            account_id=account_id,
            is_default=cls._binding_count(session, user_id) == 0,
            assigned_by_user_id=assigned_by_user_id,
        )
        session.add(binding)
        session.flush()
        return binding

    @staticmethod
    def _course_record(row: ClassCubeCourseRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "account_id": row.account_id,
            "remote_course_id": row.remote_course_id,
            "name": row.name,
            "class_code": row.class_code,
            "payload": dict(row.payload or {}),
            "synced_at": row.synced_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @classmethod
    def _apply_remote_identity(
        cls,
        row: ClassCubeAccountRow,
        remote_user_name: str,
    ) -> None:
        normalized_name = str(remote_user_name or "").strip()
        if not normalized_name:
            return
        current_remark = str(row.name or "").strip()
        previous_remote_name = str(row.remote_user_name or "").strip()
        if current_remark in {
            "",
            cls.DEFAULT_ACCOUNT_NAME,
            previous_remote_name,
        }:
            row.name = normalized_name
        row.remote_user_name = normalized_name

    @staticmethod
    def _item_record(
        row: ClassCubeCheckinItemRow,
    ) -> dict[str, Any]:
        return {
            "id": row.id,
            "course_id": row.course_id,
            "remote_item_id": row.remote_item_id,
            "title": row.title,
            "mode": row.mode,
            "remote_module": row.remote_module,
            "form_action": row.form_action,
            "form_schema": dict(row.form_schema or {}),
            "status": row.status,
            "start_at": row.start_at,
            "end_at": row.end_at,
            "synced_at": row.synced_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _task_record(row):
        record = {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
        }
        try:
            record["schedule_times"] = json.loads(
                record.pop("schedule_times_json", "[]") or "[]"
            )
        except (TypeError, json.JSONDecodeError):
            record["schedule_times"] = []
        record["date_mode"] = record.get("date_mode") or "daily"
        record["run_dates"] = list(record.get("run_dates") or [])
        record["skip_dates"] = list(record.get("skip_dates") or [])
        record["skip_weekends"] = bool(record.get("skip_weekends", False))
        record["auto_disable_after_finish"] = bool(
            record.get("auto_disable_after_finish", False)
        )
        return record

    @staticmethod
    def _run_record(row):
        return {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
        }

    @staticmethod
    def _task_run_scope(session, task_id):
        task = session.get(ClassCubeTaskRow, task_id)
        if task is None:
            raise ClassCubeNotFound("班级魔方任务不存在")
        return {
            "source": "task",
            "owner_user_id": task.owner_user_id,
            "account_id": task.account_id,
            "course_id": task.course_id,
        }

    @staticmethod
    def _scoped_account_query(
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> Select:
        query = select(ClassCubeAccountRow).where(
            ClassCubeAccountRow.id == account_id
        )
        if not is_admin:
            query = query.join(
                ClassCubeAccountBindingRow,
                ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
            ).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id
            )
        return query

    @staticmethod
    def _scoped_course_query(
        course_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> Select:
        query = (
            select(ClassCubeCourseRow)
            .join(
                ClassCubeAccountRow,
                ClassCubeCourseRow.account_id
                == ClassCubeAccountRow.id,
            )
            .where(ClassCubeCourseRow.id == course_id)
        )
        if not is_admin:
            query = query.join(
                ClassCubeAccountBindingRow,
                ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
            ).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id
            )
        return query

    @staticmethod
    def _scoped_item_query(
        item_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> Select:
        query = (
            select(ClassCubeCheckinItemRow)
            .join(
                ClassCubeCourseRow,
                ClassCubeCheckinItemRow.course_id
                == ClassCubeCourseRow.id,
            )
            .join(
                ClassCubeAccountRow,
                ClassCubeCourseRow.account_id
                == ClassCubeAccountRow.id,
            )
            .where(ClassCubeCheckinItemRow.id == item_id)
        )
        if not is_admin:
            query = query.join(
                ClassCubeAccountBindingRow,
                ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
            ).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id
            )
        return query

    def list_accounts(
        self,
        actor_user_id: int,
        is_admin: bool,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            query = select(ClassCubeAccountRow, ClassCubeAccountBindingRow)
            if is_admin:
                if owner_user_id is not None:
                    query = query.join(
                        ClassCubeAccountBindingRow,
                        ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
                    ).where(ClassCubeAccountBindingRow.user_id == owner_user_id)
                else:
                    query = query.outerjoin(
                        ClassCubeAccountBindingRow,
                        ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
                    )
            else:
                query = query.join(
                    ClassCubeAccountBindingRow,
                    ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
                ).where(ClassCubeAccountBindingRow.user_id == actor_user_id)
            pairs = session.execute(
                query.order_by(
                    ClassCubeAccountBindingRow.is_default.desc(),
                    ClassCubeAccountRow.id,
                )
            ).all()
            records: dict[int, dict[str, Any]] = {}
            for row, binding in pairs:
                record_binding = (
                    binding
                    if binding is not None and (
                        not is_admin or owner_user_id == binding.user_id
                    ) else None
                )
                records.setdefault(
                    int(row.id), self._account_record(row, record_binding)
                )
            return list(records.values())

    def get_account(
        self,
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            binding = session.scalar(select(ClassCubeAccountBindingRow).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id,
                ClassCubeAccountBindingRow.account_id == row.id,
            ))
            return self._account_record(row, binding)

    def account_access(self, user_id: int, is_admin: bool) -> dict[str, Any]:
        with self.database.session() as session:
            count = self._binding_count(session, user_id)
            limit = None if is_admin else self._account_limit(session, user_id)
            return {
                "account_limit": limit,
                "account_count": count,
                "can_add_account": limit is None or count < limit,
            }

    def validate_account_limit(self, user_id: int, limit: int | None) -> int:
        with self.database.session() as session:
            count = self._binding_count(session, user_id)
            if limit is not None and count > limit:
                raise ValueError(
                    f"该用户当前已绑定 {count} 个班级魔方账号，"
                    f"请先解除 {count - limit} 个绑定再降低额度"
                )
            return count

    def consume_location_search_quota(
        self,
        user_id: int,
        is_admin: bool,
        *,
        today: date | None = None,
    ) -> dict[str, int | None]:
        current_date = today or date.today()
        if is_admin:
            return {"limit": None, "used": 0, "remaining": None}
        with self.database.session() as session:
            policy = session.scalar(
                select(UserFeaturePolicyRow)
                .where(UserFeaturePolicyRow.user_id == int(user_id))
                .with_for_update()
            )
            limit = (
                policy.location_search_daily_limit
                if policy is not None
                else None
            )
            if limit is None:
                return {"limit": None, "used": 0, "remaining": None}
            if policy.location_search_date != current_date:
                policy.location_search_date = current_date
                policy.location_search_used = 0
            used = int(policy.location_search_used or 0)
            if used >= limit:
                raise ValueError(
                    f"今日地址搜索次数已用完（{used}/{limit}），"
                    "请明天再试或联系管理员调整额度"
                )
            policy.location_search_used = used + 1
            policy.updated_at = datetime.now()
            session.flush()
            return {
                "limit": int(limit),
                "used": used + 1,
                "remaining": max(int(limit) - used - 1, 0),
            }

    def assert_can_add_account(self, user_id: int, is_admin: bool) -> None:
        if is_admin:
            return
        with self.database.session() as session:
            self._assert_binding_capacity(session, user_id)

    def assign_account_to_user(
        self,
        account_id: int,
        user_id: int,
        assigned_by_user_id: int,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ClassCubeAccountRow, account_id)
            if row is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            binding = self._ensure_binding(
                session,
                user_id=user_id,
                account_id=account_id,
                assigned_by_user_id=assigned_by_user_id,
            )
            return self._account_record(row, binding)

    def remove_user_bindings(self, user_id: int) -> None:
        with self.database.session() as session:
            session.execute(delete(ClassCubeTaskRow).where(
                ClassCubeTaskRow.owner_user_id == user_id
            ))
            session.execute(delete(ClassCubeAccountBindingRow).where(
                ClassCubeAccountBindingRow.user_id == user_id
            ))

    def upsert_scanned_account(
        self,
        owner_user_id: int,
        identity: dict[str, Any],
        cookie: str,
        *,
        account_id: int | None = None,
        actor_user_id: int | None = None,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        now = datetime.now()
        remote_user_name = str(
            identity.get("remote_user_name")
            or identity.get("name")
            or ""
        ).strip()
        remote_uid = str(identity.get("remote_uid") or "").strip()
        if not remote_uid:
            raise ValueError("无法确认班级魔方账号 UID，请重新扫码")
        with self.database.session() as session:
            if account_id is None:
                row = session.scalar(select(ClassCubeAccountRow).where(
                    ClassCubeAccountRow.remote_uid == remote_uid
                ).with_for_update())
                if row is None:
                    self._assert_binding_capacity(session, owner_user_id)
                    row = ClassCubeAccountRow(
                        owner_user_id=owner_user_id,
                        name=remote_user_name or self.DEFAULT_ACCOUNT_NAME,
                        remote_user_name=remote_user_name,
                        remote_uid=remote_uid,
                        cookie=cookie,
                        status="active",
                        last_login_at=now,
                    )
                    session.add(row)
                    session.flush()
                binding = self._ensure_binding(
                    session,
                    user_id=owner_user_id,
                    account_id=row.id,
                    assigned_by_user_id=actor_user_id or owner_user_id,
                )
            else:
                scoped_actor_id = (
                    owner_user_id
                    if actor_user_id is None
                    else actor_user_id
                )
                row = session.scalar(
                    self._scoped_account_query(
                        account_id,
                        scoped_actor_id,
                        is_admin,
                    )
                )
                if row is None:
                    raise ClassCubeNotFound(
                        "班级魔方账号不存在"
                    )
                if row.remote_uid and row.remote_uid != remote_uid:
                    raise ValueError(
                        "本次扫码登录的班级魔方账号与当前账号不一致"
                    )
                duplicate = session.scalar(select(ClassCubeAccountRow.id).where(
                    ClassCubeAccountRow.remote_uid == remote_uid,
                    ClassCubeAccountRow.id != row.id,
                ))
                if duplicate is not None:
                    raise ValueError(
                        "该班级魔方 UID 已绑定其他账号，请使用扫码添加进行复用"
                    )
                row.remote_uid = remote_uid
                binding = self._ensure_binding(
                    session,
                    user_id=owner_user_id,
                    account_id=row.id,
                    assigned_by_user_id=actor_user_id or owner_user_id,
                )
                row.cookie = cookie
                row.status = "active"
                row.last_login_at = now
                row.updated_at = now
                session.flush()
            self._apply_remote_identity(row, remote_user_name)
            row.cookie = cookie
            row.status = "active"
            row.last_login_at = now
            row.updated_at = now
            session.flush()
            return self._account_record(row, binding)

    def bind_existing_scanned_account(
        self,
        *,
        owner_user_id: int,
        remote_uid: str,
        remote_user_name: str,
        cookie: str,
        actor_user_id: int,
    ) -> dict[str, Any]:
        now = datetime.now()
        with self.database.session() as session:
            row = session.scalar(select(ClassCubeAccountRow).where(
                ClassCubeAccountRow.remote_uid == str(remote_uid)
            ).with_for_update())
            if row is None:
                raise ClassCubeNotFound("班级魔方账号不存在，请重新扫码")
            binding = self._ensure_binding(
                session,
                user_id=owner_user_id,
                account_id=row.id,
                assigned_by_user_id=actor_user_id,
            )
            self._apply_remote_identity(row, remote_user_name)
            row.cookie = cookie
            row.status = "active"
            row.last_login_at = now
            row.updated_at = now
            session.flush()
            return self._account_record(row, binding)

    def update_account_name(
        self,
        account_id: int,
        name: str,
        actor_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            row.name = name
            row.updated_at = datetime.now()
            session.flush()
            return self._account_record(row)

    def mark_account_expired(
        self,
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound(
                    "班级魔方账号不存在"
                )
            row.status = "expired"
            row.updated_at = datetime.now()
            session.query(ClassCubeTaskRow).filter(
                ClassCubeTaskRow.account_id == account_id
            ).update(
                {"enabled": False, "updated_at": datetime.now()},
                synchronize_session=False,
            )
            session.flush()
            return self._account_record(row)

    def delete_account(
        self,
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> None:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            if is_admin:
                session.delete(row)
                return
            session.execute(delete(ClassCubeTaskRow).where(
                ClassCubeTaskRow.owner_user_id == actor_user_id,
                ClassCubeTaskRow.account_id == account_id,
            ))
            session.execute(delete(ClassCubeAccountBindingRow).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id,
                ClassCubeAccountBindingRow.account_id == account_id,
            ))
            replacement = session.scalar(
                select(ClassCubeAccountBindingRow)
                .where(ClassCubeAccountBindingRow.user_id == actor_user_id)
                .order_by(ClassCubeAccountBindingRow.id)
            )
            if replacement is not None and not session.scalar(select(
                func.count(ClassCubeAccountBindingRow.id)
            ).where(
                ClassCubeAccountBindingRow.user_id == actor_user_id,
                ClassCubeAccountBindingRow.is_default.is_(True),
            )):
                replacement.is_default = True

    def delete_accounts(
        self,
        account_ids: Iterable[int],
        actor_user_id: int,
        is_admin: bool,
    ) -> int:
        normalized_ids = sorted(set(account_ids))
        with self.database.session() as session:
            query = select(ClassCubeAccountRow).where(
                ClassCubeAccountRow.id.in_(normalized_ids)
            )
            if not is_admin:
                query = query.join(
                    ClassCubeAccountBindingRow,
                    ClassCubeAccountBindingRow.account_id == ClassCubeAccountRow.id,
                ).where(ClassCubeAccountBindingRow.user_id == actor_user_id)
            rows = session.scalars(query).all()
            if len(rows) != len(normalized_ids):
                raise ClassCubeNotFound("班级魔方账号不存在")
            if is_admin:
                for row in rows:
                    session.delete(row)
            else:
                session.execute(delete(ClassCubeTaskRow).where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id,
                    ClassCubeTaskRow.account_id.in_(normalized_ids),
                ))
                session.execute(delete(ClassCubeAccountBindingRow).where(
                    ClassCubeAccountBindingRow.user_id == actor_user_id,
                    ClassCubeAccountBindingRow.account_id.in_(normalized_ids),
                ))
                replacement = session.scalar(
                    select(ClassCubeAccountBindingRow)
                    .where(ClassCubeAccountBindingRow.user_id == actor_user_id)
                    .order_by(ClassCubeAccountBindingRow.id)
                )
                has_default = session.scalar(select(
                    func.count(ClassCubeAccountBindingRow.id)
                ).where(
                    ClassCubeAccountBindingRow.user_id == actor_user_id,
                    ClassCubeAccountBindingRow.is_default.is_(True),
                ))
                if replacement is not None and not has_default:
                    replacement.is_default = True
            session.flush()
            return len(rows)

    def get_course(
        self,
        course_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_course_query(
                    course_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound("班级魔方课程不存在")
            return self._course_record(row)

    def list_courses(
        self,
        account_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            account = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if account is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            rows = session.scalars(
                select(ClassCubeCourseRow)
                .where(
                    ClassCubeCourseRow.account_id == account_id
                )
                .order_by(ClassCubeCourseRow.id)
            ).all()
            return [self._course_record(row) for row in rows]

    def list_courses_by_remote_course(
        self,
        remote_course_id: str,
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            statement = (
                select(ClassCubeCourseRow)
                .join(
                    ClassCubeAccountRow,
                    ClassCubeCourseRow.account_id
                    == ClassCubeAccountRow.id,
                )
                .where(
                    ClassCubeCourseRow.remote_course_id
                    == str(remote_course_id),
                    ClassCubeAccountRow.status == "active",
                    ClassCubeAccountRow.cookie != "",
                )
                .order_by(ClassCubeCourseRow.id)
            )
            rows = session.scalars(statement).all()
            return [self._course_record(row) for row in rows]

    def list_active_courses(self) -> list[dict[str, Any]]:
        with self.database.session() as session:
            statement = (
                select(ClassCubeCourseRow)
                .join(
                    ClassCubeAccountRow,
                    ClassCubeCourseRow.account_id
                    == ClassCubeAccountRow.id,
                )
                .where(
                    ClassCubeAccountRow.status == "active",
                    ClassCubeAccountRow.cookie != "",
                )
                .order_by(ClassCubeCourseRow.id)
            )
            return [
                self._course_record(row)
                for row in session.scalars(statement).all()
            ]

    def upsert_courses(
        self,
        account_id: int,
        courses: Iterable[ParsedCourse],
        actor_user_id: int,
        is_admin: bool,
    ) -> list[dict[str, Any]]:
        now = datetime.now()
        with self.database.session() as session:
            account = session.scalar(
                self._scoped_account_query(
                    account_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if account is None:
                raise ClassCubeNotFound("班级魔方账号不存在")
            existing_rows = session.scalars(
                select(ClassCubeCourseRow).where(
                    ClassCubeCourseRow.account_id == account_id
                )
            ).all()
            by_remote_id = {
                row.remote_course_id: row for row in existing_rows
            }
            for course in courses:
                remote_course_id = str(course.remote_course_id)
                row = by_remote_id.get(remote_course_id)
                if row is None:
                    row = ClassCubeCourseRow(
                        account_id=account_id,
                        remote_course_id=remote_course_id,
                        name=course.name,
                        class_code=course.class_code,
                        payload={},
                        synced_at=now,
                    )
                    session.add(row)
                    by_remote_id[remote_course_id] = row
                else:
                    row.name = course.name
                    row.class_code = course.class_code
                    row.synced_at = now
                    row.updated_at = now
            session.flush()
            rows = session.scalars(
                select(ClassCubeCourseRow)
                .where(
                    ClassCubeCourseRow.account_id == account_id
                )
                .order_by(ClassCubeCourseRow.id)
            ).all()
            return [self._course_record(row) for row in rows]

    def get_item(
        self,
        item_id: int,
        actor_user_id: int,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.scalar(
                self._scoped_item_query(
                    item_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if row is None:
                raise ClassCubeNotFound("班级魔方签到项不存在")
            return self._item_record(row)

    def list_items(
        self,
        course_id: int,
        actor_user_id: int,
        is_admin: bool,
        *,
        latest_only: bool = False,
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            course = session.scalar(
                self._scoped_course_query(
                    course_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if course is None:
                raise ClassCubeNotFound("班级魔方课程不存在")
            statement = select(ClassCubeCheckinItemRow).where(
                ClassCubeCheckinItemRow.course_id == course_id
            )
            if latest_only:
                latest_synced_at = session.scalar(
                    select(
                        func.max(
                            ClassCubeCheckinItemRow.synced_at
                        )
                    ).where(
                        ClassCubeCheckinItemRow.course_id
                        == course_id
                    )
                )
                if latest_synced_at is not None:
                    latest_day = latest_synced_at.date()
                    statement = statement.where(
                        ClassCubeCheckinItemRow.synced_at
                        >= datetime.combine(latest_day, time.min),
                        ClassCubeCheckinItemRow.synced_at
                        < datetime.combine(
                            latest_day + timedelta(days=1),
                            time.min,
                        ),
                    )
            rows = session.scalars(
                statement.order_by(ClassCubeCheckinItemRow.id.desc())
            ).all()
            return [self._item_record(row) for row in rows]

    def list_class_checkin_targets(
        self,
        remote_course_id: str,
        remote_item_id: str,
        remote_module: str,
        mode: str,
    ) -> list[dict[str, Any]]:
        """Return detached account/course/item records for an admin batch."""
        with self.database.session() as session:
            statement = (
                select(
                    ClassCubeAccountRow,
                    ClassCubeCourseRow,
                    ClassCubeCheckinItemRow,
                )
                .join(
                    ClassCubeCourseRow,
                    ClassCubeCourseRow.account_id
                    == ClassCubeAccountRow.id,
                )
                .join(
                    ClassCubeCheckinItemRow,
                    ClassCubeCheckinItemRow.course_id
                    == ClassCubeCourseRow.id,
                )
                .where(
                    ClassCubeAccountRow.status == "active",
                    ClassCubeAccountRow.cookie != "",
                    ClassCubeCourseRow.remote_course_id
                    == str(remote_course_id),
                    ClassCubeCheckinItemRow.remote_item_id
                    == str(remote_item_id),
                    ClassCubeCheckinItemRow.remote_module
                    == str(remote_module),
                    ClassCubeCheckinItemRow.mode == str(mode),
                    ClassCubeCheckinItemRow.status == "active",
                )
                .order_by(ClassCubeAccountRow.id)
            )
            rows = session.execute(statement).all()
            return [
                {
                    "account": self._account_record(account),
                    "course": self._course_record(course),
                    "item": self._item_record(item),
                }
                for account, course, item in rows
            ]

    def upsert_items(
        self,
        course_id: int,
        bundles: Iterable[RemoteItemBundle],
        actor_user_id: int,
        is_admin: bool,
        *,
        close_source: str | None = None,
    ) -> list[dict[str, Any]]:
        now = datetime.now()
        with self.database.session() as session:
            course = session.scalar(
                self._scoped_course_query(
                    course_id,
                    actor_user_id,
                    is_admin,
                )
            )
            if course is None:
                raise ClassCubeNotFound("班级魔方课程不存在")
            existing_rows = session.scalars(
                select(ClassCubeCheckinItemRow).where(
                    ClassCubeCheckinItemRow.course_id == course_id
                )
            ).all()
            by_remote_key = {
                (row.remote_item_id, row.remote_module): row
                for row in existing_rows
            }
            bundles = list(bundles)
            seen_keys = set()
            for bundle in bundles:
                remote_key = (
                    str(bundle.item.remote_item_id),
                    str(bundle.item.remote_module),
                )
                if (
                    close_source is None
                    or (
                        close_source == "daka"
                        and remote_key[1] == "daka"
                    )
                    or (
                        close_source == "punchs"
                        and remote_key[1] != "daka"
                    )
                ):
                    seen_keys.add(remote_key)
                row = by_remote_key.get(remote_key)
                form_schema = {
                    "method": bundle.form.method,
                    "mode": bundle.form.mode,
                    "hidden_fields": dict(
                        (
                            key,
                            value,
                        )
                        for key, value
                        in bundle.form.hidden_fields.items()
                        if str(key).strip().lower()
                        not in PASSWORD_FIELD_ALIASES
                    ),
                    "password_field": (
                        bundle.form.password_field
                    ),
                    "file_field": bundle.form.file_field,
                    "item_id_field": (
                        bundle.form.item_id_field
                    ),
                    "latitude_field": (
                        bundle.form.latitude_field
                    ),
                    "longitude_field": (
                        bundle.form.longitude_field
                    ),
                    "accuracy_field": (
                        bundle.form.accuracy_field
                    ),
                    "gps_address_field": (
                        bundle.form.gps_address_field
                    ),
                    "photo_resource_field": (
                        bundle.form.photo_resource_field
                    ),
                    "submit_capable": (
                        bundle.form.submit_capable
                    ),
                    "upload_action": (
                        bundle.form.upload_action
                    ),
                    "upload_method": (
                        bundle.form.upload_method
                    ),
                    "upload_file_field": (
                        bundle.form.upload_file_field
                    ),
                    "upload_response_key": (
                        bundle.form.upload_response_key
                    ),
                }
                mode = (
                    bundle.form.mode
                    if bundle.form.mode != "unknown"
                    else bundle.item.mode_hint
                )
                if row is None:
                    row = ClassCubeCheckinItemRow(
                        course_id=course_id,
                        remote_item_id=remote_key[0],
                        title=bundle.item.title,
                        mode=mode,
                        remote_module=remote_key[1],
                        form_action=bundle.form.action,
                        form_schema=form_schema,
                        status="active",
                        synced_at=now,
                    )
                    session.add(row)
                    by_remote_key[remote_key] = row
                else:
                    row.title = bundle.item.title or row.title
                    row.mode = mode
                    row.form_action = bundle.form.action
                    row.form_schema = form_schema
                    row.status = "active"
                    row.synced_at = now
                    row.updated_at = now
            if close_source is not None:
                for row in existing_rows:
                    belongs_to_source = (
                        row.remote_module == "daka"
                        if close_source == "daka"
                        else row.remote_module != "daka"
                    )
                    if (
                        belongs_to_source
                        and (row.remote_item_id, row.remote_module)
                        not in seen_keys
                    ):
                        row.status = "closed"
                        row.updated_at = now
            session.flush()
            rows = session.scalars(
                select(ClassCubeCheckinItemRow)
                .where(
                    ClassCubeCheckinItemRow.course_id == course_id
                )
                .order_by(ClassCubeCheckinItemRow.id)
            ).all()
            return [self._item_record(row) for row in rows]

    def sync_source_items(
        self, course_id, source_module, bundles,
        actor_user_id, is_admin
    ):
        return self.upsert_items(
            course_id, bundles, actor_user_id, is_admin,
            close_source=source_module,
        )

    def list_tasks(
        self, actor_user_id, is_admin, owner_user_id=None, *, enabled=None,
        due_at=None,
    ):
        with self.database.session() as session:
            query = select(ClassCubeTaskRow)
            if is_admin and owner_user_id is not None:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == owner_user_id
                )
            elif not is_admin:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id
                )
            if enabled is not None:
                query = query.where(ClassCubeTaskRow.enabled == enabled)
            if due_at is not None:
                query = query.where(
                    (ClassCubeTaskRow.last_scan_at.is_(None))
                    | (
                        ClassCubeTaskRow.last_scan_at
                        <= due_at - timedelta(seconds=30)
                    )
                )
            rows = session.scalars(query.order_by(ClassCubeTaskRow.id)).all()
            return [self._task_record(row) for row in rows]

    def claim_task_scan(self, task_id, now=None):
        now = now or datetime.now()
        threshold = now - timedelta(seconds=30)
        with self.database.session() as session:
            result = session.execute(
                update(ClassCubeTaskRow)
                .where(
                    ClassCubeTaskRow.id == task_id,
                    ClassCubeTaskRow.enabled.is_(True),
                    (ClassCubeTaskRow.last_scan_at.is_(None))
                    | (ClassCubeTaskRow.last_scan_at <= threshold),
                )
                .values(last_scan_at=now, updated_at=now)
            )
            return result.rowcount == 1

    def get_task(self, task_id, actor_user_id, is_admin):
        with self.database.session() as session:
            query = select(ClassCubeTaskRow).where(
                ClassCubeTaskRow.id == task_id
            )
            if not is_admin:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id
                )
            row = session.scalar(query)
            if row is None:
                raise ClassCubeNotFound("班级魔方任务不存在")
            return self._task_record(row)

    def save_task(
        self, values, actor_user_id, is_admin, task_id=None
    ):
        with self.database.session() as session:
            owner_id = int(values.get("owner_user_id") or actor_user_id)
            if not is_admin and owner_id != actor_user_id:
                raise ClassCubeNotFound("班级魔方账号不存在")
            account = session.scalar(
                select(ClassCubeAccountRow).where(
                    ClassCubeAccountRow.id == values["account_id"],
                )
            )
            if account is not None and (not is_admin or owner_id != actor_user_id):
                binding = session.scalar(select(ClassCubeAccountBindingRow.id).where(
                    ClassCubeAccountBindingRow.user_id == owner_id,
                    ClassCubeAccountBindingRow.account_id == account.id,
                ))
                if binding is None:
                    account = None
            course = session.scalar(
                select(ClassCubeCourseRow).where(
                    ClassCubeCourseRow.id == values["course_id"],
                    ClassCubeCourseRow.account_id == values["account_id"],
                )
            )
            if account is None or course is None:
                raise ClassCubeNotFound("班级魔方账号或课程不存在")
            if values.get("enabled") and account.status != "active":
                raise ValueError("登录失效的账号不能启用任务")
            if task_id is None:
                row = ClassCubeTaskRow(owner_user_id=owner_id)
                session.add(row)
            else:
                query = select(ClassCubeTaskRow).where(
                    ClassCubeTaskRow.id == task_id
                )
                if not is_admin:
                    query = query.where(
                        ClassCubeTaskRow.owner_user_id == actor_user_id
                    )
                row = session.scalar(query)
                if row is None:
                    raise ClassCubeNotFound("班级魔方任务不存在")
            for key, value in values.items():
                if key in {
                    "account_id", "course_id", "name", "enabled",
                    "latitude", "longitude", "accuracy", "photo_path", "photo_res",
                    "password", "start_date", "end_date",
                    "date_mode", "run_dates", "skip_dates",
                    "skip_weekends", "auto_disable_after_finish",
                    "notify_wecom",
                }:
                    setattr(row, key, value)
            if "schedule_times" in values:
                row.schedule_times_json = json.dumps(
                    values["schedule_times"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            row.poll_interval_seconds = 30
            row.updated_at = datetime.now()
            session.flush()
            return self._task_record(row)

    def complete_task_if_final_occurrence(
        self, task_id, scheduled_for, completion_result
    ):
        scheduled_for = scheduled_for.replace(microsecond=0, tzinfo=None)
        with self.database.session() as session:
            row = session.scalar(
                select(ClassCubeTaskRow)
                .where(ClassCubeTaskRow.id == task_id)
                .with_for_update()
            )
            if (
                row is None
                or not row.enabled
                or not row.auto_disable_after_finish
                or (row.date_mode or "daily") != "specific"
            ):
                return None
            task = self._task_record(row)
            last_occurrence = get_last_effective_occurrence(task)
            if last_occurrence is None or last_occurrence != scheduled_for:
                return None
            row.enabled = False
            row.updated_at = datetime.now()
            session.flush()
            result = self._task_record(row)
            result["completion_result"] = completion_result
            return result

    def claim_task_schedule(self, task_id, schedule_key, now=None):
        now = now or datetime.now()
        with self.database.session() as session:
            result = session.execute(
                update(ClassCubeTaskRow)
                .where(
                    ClassCubeTaskRow.id == task_id,
                    ClassCubeTaskRow.enabled.is_(True),
                    ClassCubeTaskRow.last_schedule_key != schedule_key,
                )
                .values(
                    last_schedule_key=schedule_key,
                    last_scan_at=now,
                    updated_at=now,
                )
            )
            return result.rowcount == 1

    def delete_tasks(self, task_ids, actor_user_id, is_admin):
        ids = list(dict.fromkeys(int(value) for value in task_ids))
        with self.database.session() as session:
            query = select(ClassCubeTaskRow).where(
                ClassCubeTaskRow.id.in_(ids)
            )
            if not is_admin:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id
                )
            rows = session.scalars(query).all()
            if len(rows) != len(ids):
                raise ClassCubeNotFound("班级魔方任务不存在")
            for row in rows:
                session.delete(row)
        return len(ids)

    def try_claim(
        self, task_id, item_id, remote_item_id, remote_module,
        *, lease_seconds=120
    ):
        now = datetime.now()
        lease_until = now + timedelta(seconds=lease_seconds)
        lease_token = uuid.uuid4().hex
        try:
            with self.database.session() as session:
                row = session.scalar(
                    select(ClassCubeTaskItemClaimRow)
                    .where(
                        ClassCubeTaskItemClaimRow.task_id == task_id,
                        ClassCubeTaskItemClaimRow.remote_module
                        == remote_module,
                        ClassCubeTaskItemClaimRow.remote_item_id
                        == remote_item_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    row = ClassCubeTaskItemClaimRow(
                        task_id=task_id,
                        checkin_item_id=item_id,
                        remote_item_id=remote_item_id,
                        remote_module=remote_module,
                        state="processing",
                        lease_until=lease_until,
                        lease_token=lease_token,
                        phase="pre_submit",
                    )
                    session.add(row)
                elif (
                    row.state == "processing"
                    and (row.lease_until is None or row.lease_until <= now)
                    and row.phase == "submitting"
                ):
                    item = session.get(
                        ClassCubeCheckinItemRow,
                        row.checkin_item_id,
                    )
                    run_scope = self._task_run_scope(
                        session, row.task_id
                    )
                    run = ClassCubeTaskRunRow(
                        task_id=row.task_id,
                        **run_scope,
                        checkin_item_id=row.checkin_item_id,
                        remote_item_id=row.remote_item_id,
                        mode=(
                            item.mode if item is not None else "unknown"
                        ),
                        status="unknown_result",
                        message="任务在提交阶段中断，结果需要人工确认",
                        response_summary={},
                        started_at=row.updated_at or row.created_at,
                        finished_at=now,
                    )
                    session.add(run)
                    session.flush()
                    row.state = "unknown"
                    row.last_run_id = run.id
                    row.lease_until = None
                    row.lease_token = ""
                    row.updated_at = now
                    return None
                elif not (
                    row.state == "retryable"
                    or (
                        row.state == "processing"
                        and (row.lease_until is None or row.lease_until <= now)
                    )
                ):
                    return None
                else:
                    row.state = "processing"
                    row.checkin_item_id = item_id
                    row.lease_until = lease_until
                    row.lease_token = lease_token
                    row.phase = "pre_submit"
                    row.updated_at = now
                session.flush()
                return {
                    "id": row.id, "state": row.state,
                    "lease_until": row.lease_until,
                    "lease_token": row.lease_token,
                    "started_at": now,
                }
        except IntegrityError:
            return None

    def mark_claim_submitting(self, claim_id, lease_token):
        now = datetime.now()
        with self.database.session() as session:
            result = session.execute(
                update(ClassCubeTaskItemClaimRow)
                .where(
                    ClassCubeTaskItemClaimRow.id == claim_id,
                    ClassCubeTaskItemClaimRow.state == "processing",
                    ClassCubeTaskItemClaimRow.phase == "pre_submit",
                    ClassCubeTaskItemClaimRow.lease_token == lease_token,
                )
                .values(phase="submitting", updated_at=now)
            )
            return result.rowcount == 1

    def finish_claim(
        self, claim_id, task_id, item_id, remote_item_id, remote_module,
        state, run_status, message="", mode="unknown",
        *,
        expected_lease_token,
        started_at=None,
    ):
        now = datetime.now()
        with self.database.session() as session:
            claim = session.scalar(
                select(ClassCubeTaskItemClaimRow)
                .where(
                    ClassCubeTaskItemClaimRow.id == claim_id,
                    ClassCubeTaskItemClaimRow.task_id == task_id,
                    ClassCubeTaskItemClaimRow.state == "processing",
                    ClassCubeTaskItemClaimRow.lease_token
                    == expected_lease_token,
                )
                .with_for_update()
            )
            if claim is None:
                raise ClassCubeNotFound("签到声明不存在")
            run_scope = self._task_run_scope(session, task_id)
            run = ClassCubeTaskRunRow(
                task_id=task_id,
                **run_scope,
                checkin_item_id=item_id,
                remote_item_id=remote_item_id,
                mode=mode,
                status=run_status,
                message=" ".join(str(message).split())[:500],
                response_summary={},
                started_at=started_at or now,
                finished_at=now,
            )
            session.add(run)
            session.flush()
            claim.state = state
            claim.last_run_id = run.id
            claim.lease_until = None
            claim.lease_token = ""
            claim.updated_at = now
            session.flush()
            return self._run_record(run)

    def confirm_claim_retry(self, claim_id, actor_user_id, is_admin):
        with self.database.session() as session:
            query = (
                select(ClassCubeTaskItemClaimRow)
                .join(ClassCubeTaskRow)
                .where(ClassCubeTaskItemClaimRow.id == claim_id)
            )
            if not is_admin:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id
                )
            row = session.scalar(query.with_for_update())
            if row is None:
                raise ClassCubeNotFound("签到声明不存在")
            if row.state != "unknown":
                raise ValueError("只有未知结果可确认重试")
            row.state = "retryable"
            row.updated_at = datetime.now()
            return True

    def record_task_run(
        self,
        task_id,
        status,
        message,
        response_summary,
        started_at,
    ):
        now = datetime.now()
        with self.database.session() as session:
            run_scope = self._task_run_scope(session, task_id)
            run = ClassCubeTaskRunRow(
                task_id=task_id,
                **run_scope,
                checkin_item_id=None,
                remote_item_id="",
                mode="task",
                status=str(status)[:32],
                message=" ".join(str(message).split())[:500],
                response_summary=dict(response_summary or {}),
                started_at=started_at or now,
                finished_at=now,
            )
            session.add(run)
            session.flush()
            return self._run_record(run)

    def record_manual_run(
        self,
        *,
        owner_user_id,
        account_id,
        course_id,
        checkin_item_id,
        remote_item_id,
        mode,
        status,
        message,
        response_summary,
        started_at,
    ):
        now = datetime.now()
        with self.database.session() as session:
            run = ClassCubeTaskRunRow(
                task_id=None,
                source="course_manual",
                owner_user_id=owner_user_id,
                account_id=account_id,
                course_id=course_id,
                checkin_item_id=checkin_item_id,
                remote_item_id=str(remote_item_id)[:128],
                mode=str(mode)[:32],
                status=str(status)[:32],
                message=" ".join(str(message).split())[:500],
                response_summary=dict(response_summary or {}),
                started_at=started_at or now,
                finished_at=now,
            )
            session.add(run)
            session.flush()
            return self._run_record(run)

    def list_runs(
        self, actor_user_id, is_admin, owner_user_id=None,
        account_id=None, course_id=None, task_id=None, status=None,
        limit=100, offset=0
    ):
        with self.database.session() as session:
            query = select(ClassCubeTaskRunRow)
            if is_admin and owner_user_id is not None:
                query = query.where(
                    ClassCubeTaskRunRow.owner_user_id == owner_user_id
                )
            elif not is_admin:
                query = query.where(
                    ClassCubeTaskRunRow.owner_user_id == actor_user_id
                )
            if account_id is not None:
                query = query.where(
                    ClassCubeTaskRunRow.account_id == account_id
                )
            if course_id is not None:
                query = query.where(
                    ClassCubeTaskRunRow.course_id == course_id
                )
            if task_id is not None:
                query = query.where(ClassCubeTaskRunRow.task_id == task_id)
            if status:
                query = query.where(ClassCubeTaskRunRow.status == status)
            rows = session.scalars(
                query.order_by(ClassCubeTaskRunRow.id.desc())
                .offset(offset).limit(min(200, max(1, limit)))
            ).all()
            account_ids = {int(row.account_id) for row in rows}
            accounts = session.scalars(
                select(ClassCubeAccountRow).where(
                    ClassCubeAccountRow.id.in_(account_ids)
                )
            ).all() if account_ids else []
            account_names = {
                int(account.id): (
                    account.name
                    or account.remote_user_name
                    or f"账号 {account.id}"
                )
                for account in accounts
            }
            records = []
            for row in rows:
                record = self._run_record(row)
                record["account_name"] = account_names.get(
                    int(row.account_id),
                    f"账号 {row.account_id}",
                )
                claim_id = session.scalar(
                    select(ClassCubeTaskItemClaimRow.id).where(
                        ClassCubeTaskItemClaimRow.last_run_id == row.id
                    )
                )
                record["claim_id"] = claim_id
                records.append(record)
            return records
