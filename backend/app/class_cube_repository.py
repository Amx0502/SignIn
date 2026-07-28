from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import Select, select

from .class_cube_client import RemoteItemBundle
from .class_cube_database import ClassCubeDatabase
from .class_cube_db_models import (
    ClassCubeAccountRow,
    ClassCubeCheckinItemRow,
    ClassCubeCourseRow,
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
            for bundle in bundles:
                remote_key = (
                    str(bundle.item.remote_item_id),
                    str(bundle.item.remote_module),
                )
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
            session.flush()
            rows = session.scalars(
                select(ClassCubeCheckinItemRow)
                .where(
                    ClassCubeCheckinItemRow.course_id == course_id
                )
                .order_by(ClassCubeCheckinItemRow.id)
            ).all()
            return [self._item_record(row) for row in rows]
