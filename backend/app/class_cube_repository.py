from datetime import datetime, timedelta
import json
from typing import Any, Iterable
import uuid

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError

from .class_cube_client import RemoteItemBundle
from .class_cube_database import ClassCubeDatabase
from .class_cube_db_models import (
    ClassCubeAccountRow,
    ClassCubeCheckinItemRow,
    ClassCubeCourseRow,
    ClassCubeTaskItemClaimRow,
    ClassCubeTaskRow,
    ClassCubeTaskRunRow,
)
from .class_cube_parser import (
    PASSWORD_FIELD_ALIASES,
    ParsedCourse,
)


class ClassCubeNotFound(LookupError):
    pass


class ClassCubeRepository:
    def __init__(self, database: ClassCubeDatabase):
        self.database = database

    @staticmethod
    def _account_record(row: ClassCubeAccountRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "owner_user_id": row.owner_user_id,
            "name": row.name,
            "remote_user_name": row.remote_user_name,
            "cookie": row.cookie,
            "status": row.status,
            "last_login_at": row.last_login_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

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
        return record

    @staticmethod
    def _run_record(row):
        return {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
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
            query = query.where(
                ClassCubeAccountRow.owner_user_id == actor_user_id
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
            query = query.where(
                ClassCubeAccountRow.owner_user_id == actor_user_id
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
            query = query.where(
                ClassCubeAccountRow.owner_user_id == actor_user_id
            )
        return query

    def list_accounts(
        self,
        actor_user_id: int,
        is_admin: bool,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            query = select(ClassCubeAccountRow)
            if is_admin:
                if owner_user_id is not None:
                    query = query.where(
                        ClassCubeAccountRow.owner_user_id
                        == owner_user_id
                    )
            else:
                query = query.where(
                    ClassCubeAccountRow.owner_user_id
                    == actor_user_id
                )
            rows = session.scalars(
                query.order_by(ClassCubeAccountRow.id)
            ).all()
            return [self._account_record(row) for row in rows]

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
            return self._account_record(row)

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
        with self.database.session() as session:
            if account_id is None:
                row = ClassCubeAccountRow(
                    owner_user_id=owner_user_id,
                    name=remote_user_name or "班级魔方账号",
                    remote_user_name=remote_user_name,
                    cookie=cookie,
                    status="active",
                    last_login_at=now,
                )
                session.add(row)
                session.flush()
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
                row.remote_user_name = (
                    remote_user_name or row.remote_user_name
                )
                row.cookie = cookie
                row.status = "active"
                row.last_login_at = now
                row.updated_at = now
                session.flush()
            return self._account_record(row)

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
            session.delete(row)

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
            rows = session.scalars(
                select(ClassCubeCheckinItemRow)
                .where(
                    ClassCubeCheckinItemRow.course_id == course_id
                )
                .order_by(ClassCubeCheckinItemRow.id)
            ).all()
            return [self._item_record(row) for row in rows]

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
                    ClassCubeAccountRow.owner_user_id == owner_id,
                )
            )
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
                    "latitude", "longitude", "accuracy", "photo_path",
                    "password", "start_date", "end_date",
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
                    run = ClassCubeTaskRunRow(
                        task_id=row.task_id,
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
            run = ClassCubeTaskRunRow(
                task_id=task_id,
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

    def list_runs(
        self, actor_user_id, is_admin, owner_user_id=None,
        account_id=None, course_id=None, task_id=None, status=None,
        limit=100, offset=0
    ):
        with self.database.session() as session:
            query = (
                select(ClassCubeTaskRunRow)
                .join(ClassCubeTaskRow)
            )
            if is_admin and owner_user_id is not None:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == owner_user_id
                )
            elif not is_admin:
                query = query.where(
                    ClassCubeTaskRow.owner_user_id == actor_user_id
                )
            if account_id is not None:
                query = query.where(ClassCubeTaskRow.account_id == account_id)
            if course_id is not None:
                query = query.where(ClassCubeTaskRow.course_id == course_id)
            if task_id is not None:
                query = query.where(ClassCubeTaskRunRow.task_id == task_id)
            if status:
                query = query.where(ClassCubeTaskRunRow.status == status)
            rows = session.scalars(
                query.order_by(ClassCubeTaskRunRow.id.desc())
                .offset(offset).limit(min(200, max(1, limit)))
            ).all()
            records = []
            for row in rows:
                record = self._run_record(row)
                claim_id = session.scalar(
                    select(ClassCubeTaskItemClaimRow.id).where(
                        ClassCubeTaskItemClaimRow.last_run_id == row.id
                    )
                )
                record["claim_id"] = claim_id
                records.append(record)
            return records
