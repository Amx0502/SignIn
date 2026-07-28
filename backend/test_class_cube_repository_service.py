import unittest
import inspect
import asyncio
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import BigInteger, create_engine, event, func, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.class_cube_client import (
    ClassCubeCookieExpired,
    ClassCubeRequestError,
    QrSessionResult,
    QrSessionView,
    RemoteItemBundle,
)
from app.class_cube_db_models import (
    ClassCubeAccountRow,
    ClassCubeBase,
    ClassCubeCheckinItemRow,
    ClassCubeCourseRow,
    ClassCubeTaskItemClaimRow,
    ClassCubeTaskRow,
    ClassCubeTaskRunRow,
)
from app.class_cube_models import account_view, item_view, qr_result_view
from app.class_cube_parser import ParsedCourse, ParsedForm, ParsedItem
from app.class_cube_repository import ClassCubeNotFound, ClassCubeRepository
from app.class_cube_router import create_class_cube_router
from app.class_cube_service import (
    ClassCubeRemoteError,
    ClassCubeService,
    ClassCubeValidationError,
)
from app import main as main_module


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


class SqliteClassCubeDatabase:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(
            self.engine,
            "connect",
            lambda connection, _record: connection.execute(
                "PRAGMA foreign_keys=ON"
            ),
        )
        ClassCubeBase.metadata.create_all(self.engine)
        self._factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.open_sessions = 0

    @contextmanager
    def session(self):
        session = self._factory()
        self.open_sessions += 1
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.open_sessions -= 1
            session.close()

    def dispose(self):
        self.engine.dispose()


class SafeProjectionTest(unittest.TestCase):
    def test_account_projection_omits_cookie_and_unlisted_fields(self):
        projected = account_view(
            {
                "id": 1,
                "owner_user_id": 2,
                "name": "我的账号",
                "remote_user_name": "张同学",
                "cookie": "remember_student_secret=secret",
                "password": "must-not-leak",
                "status": "active",
            }
        )

        self.assertEqual(
            projected,
            {
                "id": 1,
                "owner_user_id": 2,
                "name": "我的账号",
                "remote_user_name": "张同学",
                "status": "active",
                "last_login_at": None,
                "created_at": None,
                "updated_at": None,
            },
        )
        self.assertNotIn("cookie", projected)
        self.assertNotIn("password", projected)

    def test_item_projection_hides_remote_form_contract(self):
        projected = item_view(
            {
                "id": 9,
                "course_id": 3,
                "remote_item_id": "remote-9",
                "title": "晨间签到",
                "mode": "password",
                "remote_module": "daka",
                "form_action": "https://bjmf.k8n.cn/secret",
                "form_schema": {
                    "hidden_fields": {"_token": "secret"},
                    "password_field": "passcode",
                },
                "status": "active",
            }
        )

        self.assertEqual(projected["id"], 9)
        self.assertEqual(projected["mode"], "password")
        self.assertNotIn("form_action", projected)
        self.assertNotIn("form_schema", projected)
        self.assertNotIn("hidden_fields", repr(projected))

    def test_qr_result_projection_never_serializes_cookie(self):
        projected = qr_result_view(
            QrSessionResult(
                status="success",
                cookie="remember_student_secret=secret",
                redirect_url="https://bj.k8n.cn/student/uidlogin?x=1",
            )
        )

        self.assertEqual(projected["status"], "success")
        self.assertNotIn("cookie", projected)
        self.assertNotIn("secret", repr(projected))


class ClassCubeRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.database = SqliteClassCubeDatabase()
        self.repository = ClassCubeRepository(self.database)
        with self.database.session() as session:
            owner_account = ClassCubeAccountRow(
                id=1,
                owner_user_id=1,
                name="账号一",
                remote_user_name="甲",
                cookie="remember_student_owner=secret",
                status="active",
            )
            other_account = ClassCubeAccountRow(
                id=2,
                owner_user_id=2,
                name="账号二",
                remote_user_name="乙",
                cookie="remember_student_other=secret",
                status="active",
            )
            session.add_all([owner_account, other_account])
            session.flush()
            owner_course = ClassCubeCourseRow(
                id=11,
                account_id=1,
                remote_course_id="course-a",
                name="数据结构",
                class_code="A001",
                payload={"safe": True},
            )
            other_course = ClassCubeCourseRow(
                id=12,
                account_id=2,
                remote_course_id="course-b",
                name="高等数学",
                class_code="B002",
                payload={},
            )
            session.add_all([owner_course, other_course])
            session.flush()
            session.add_all(
                [
                    ClassCubeCheckinItemRow(
                        id=21,
                        course_id=11,
                        remote_item_id="item-a",
                        title="签到 A",
                        mode="gps",
                        remote_module="punchs",
                        form_action="https://bjmf.k8n.cn/hidden-a",
                        form_schema={"hidden_fields": {"_token": "a"}},
                        status="active",
                    ),
                    ClassCubeCheckinItemRow(
                        id=22,
                        course_id=12,
                        remote_item_id="item-b",
                        title="签到 B",
                        mode="password",
                        remote_module="daka",
                        form_action="https://bjmf.k8n.cn/hidden-b",
                        form_schema={"hidden_fields": {"_token": "b"}},
                        status="active",
                    ),
                ]
            )

    def tearDown(self):
        self.database.dispose()

    def test_normal_user_cannot_read_another_users_account_course_or_item(self):
        checks = (
            lambda: self.repository.get_account(2, 1, False),
            lambda: self.repository.get_course(12, 1, False),
            lambda: self.repository.get_item(22, 1, False),
        )

        for check in checks:
            with self.subTest(check=check):
                with self.assertRaises(ClassCubeNotFound):
                    check()
        self.assertEqual(self.database.open_sessions, 0)

    def test_admin_can_read_another_users_records(self):
        account = self.repository.get_account(2, 99, True)
        course = self.repository.get_course(12, 99, True)
        item = self.repository.get_item(22, 99, True)

        self.assertEqual(account["owner_user_id"], 2)
        self.assertEqual(course["account_id"], 2)
        self.assertEqual(item["course_id"], 12)
        self.assertEqual(self.database.open_sessions, 0)

    def test_account_lists_are_owner_scoped_and_admin_filterable(self):
        own = self.repository.list_accounts(1, False, owner_user_id=2)
        all_accounts = self.repository.list_accounts(99, True)
        filtered = self.repository.list_accounts(
            99,
            True,
            owner_user_id=2,
        )

        self.assertEqual([row["id"] for row in own], [1])
        self.assertEqual(
            [row["id"] for row in all_accounts],
            [1, 2],
        )
        self.assertEqual([row["id"] for row in filtered], [2])

    def test_first_scan_always_creates_and_explicit_rescan_updates_owned_id(self):
        first = self.repository.upsert_scanned_account(
            owner_user_id=1,
            identity={"remote_user_name": "同名同学"},
            cookie="remember_student_one=first",
        )
        second = self.repository.upsert_scanned_account(
            owner_user_id=1,
            identity={"remote_user_name": "同名同学"},
            cookie="remember_student_one=first",
        )
        rescanned = self.repository.upsert_scanned_account(
            owner_user_id=1,
            identity={"remote_user_name": "新姓名"},
            cookie="remember_student_one=updated",
            account_id=first["id"],
            actor_user_id=1,
            is_admin=False,
        )

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(rescanned["id"], first["id"])
        self.assertEqual(rescanned["remote_user_name"], "新姓名")
        self.assertEqual(
            self.repository.get_account(first["id"], 1, False)["cookie"],
            "remember_student_one=updated",
        )

    def test_explicit_rescan_cannot_update_unowned_account(self):
        with self.assertRaises(ClassCubeNotFound):
            self.repository.upsert_scanned_account(
                owner_user_id=1,
                identity={"remote_user_name": "攻击者"},
                cookie="remember_student_attack=secret",
                account_id=2,
                actor_user_id=1,
                is_admin=False,
            )

        account = self.repository.get_account(2, 99, True)
        self.assertEqual(account["remote_user_name"], "乙")
        self.assertEqual(
            account["cookie"],
            "remember_student_other=secret",
        )

    def test_account_note_can_be_edited_without_exposing_or_replacing_cookie(self):
        updated = self.repository.update_account_name(
            account_id=1,
            name="新的备注",
            actor_user_id=1,
            is_admin=False,
        )

        self.assertEqual(updated["name"], "新的备注")
        self.assertEqual(
            updated["cookie"],
            "remember_student_owner=secret",
        )

    def test_course_upsert_preserves_local_id_and_attached_task(self):
        with self.database.session() as session:
            session.add(
                ClassCubeTaskRow(
                    id=31,
                    owner_user_id=1,
                    account_id=1,
                    course_id=11,
                    name="保留任务",
                    enabled=True,
                    poll_interval_seconds=30,
                )
            )

        courses = self.repository.upsert_courses(
            account_id=1,
            courses=[
                ParsedCourse(
                    remote_course_id="course-a",
                    name="数据结构（更新）",
                    class_code="A009",
                ),
                ParsedCourse(
                    remote_course_id="course-new",
                    name="操作系统",
                    class_code="A010",
                ),
            ],
            actor_user_id=1,
            is_admin=False,
        )

        by_remote_id = {
            course["remote_course_id"]: course for course in courses
        }
        self.assertEqual(by_remote_id["course-a"]["id"], 11)
        self.assertEqual(
            by_remote_id["course-a"]["name"],
            "数据结构（更新）",
        )
        with self.database.session() as session:
            task = session.get(ClassCubeTaskRow, 31)
            self.assertEqual(task.course_id, 11)

    def test_item_upsert_preserves_local_id_and_run_history(self):
        with self.database.session() as session:
            task = ClassCubeTaskRow(
                id=32,
                owner_user_id=1,
                account_id=1,
                course_id=11,
                name="历史任务",
                enabled=True,
                poll_interval_seconds=30,
            )
            run = ClassCubeTaskRunRow(
                id=41,
                task_id=32,
                checkin_item_id=21,
                remote_item_id="item-a",
                mode="gps",
                status="success",
                message="已完成",
            )
            session.add_all([task, run])

        items = self.repository.upsert_items(
            course_id=11,
            bundles=[
                RemoteItemBundle(
                    item=ParsedItem(
                        remote_item_id="item-a",
                        course_id="course-a",
                        title="签到 A（更新）",
                        remote_module="punchs",
                        mode_hint="gps",
                    ),
                    form=ParsedForm(
                        action=(
                            "https://bjmf.k8n.cn/student/"
                            "punchs/course/course-a/item-a"
                        ),
                        method="post",
                        mode="gps",
                        hidden_fields={"_token": "new-secret"},
                    ),
                )
            ],
            actor_user_id=1,
            is_admin=False,
        )

        self.assertEqual(items[0]["id"], 21)
        self.assertEqual(items[0]["title"], "签到 A（更新）")
        with self.database.session() as session:
            run = session.get(ClassCubeTaskRunRow, 41)
            self.assertEqual(run.checkin_item_id, 21)

    def test_delete_account_cascades_its_full_local_tree_only(self):
        with self.database.session() as session:
            task = ClassCubeTaskRow(
                id=33,
                owner_user_id=1,
                account_id=1,
                course_id=11,
                name="级联任务",
                enabled=True,
                poll_interval_seconds=30,
            )
            run = ClassCubeTaskRunRow(
                id=42,
                task_id=33,
                checkin_item_id=21,
                remote_item_id="item-a",
                mode="gps",
                status="success",
                message="完成",
            )
            claim = ClassCubeTaskItemClaimRow(
                id=51,
                task_id=33,
                checkin_item_id=21,
                remote_item_id="item-a",
                state="succeeded",
                last_run=run,
            )
            session.add_all([task, run, claim])

        self.repository.delete_account(1, 1, False)

        with self.database.session() as session:
            for model in (
                ClassCubeAccountRow,
                ClassCubeCourseRow,
                ClassCubeCheckinItemRow,
                ClassCubeTaskRow,
                ClassCubeTaskRunRow,
                ClassCubeTaskItemClaimRow,
            ):
                remaining = session.scalar(
                    select(func.count()).select_from(model)
                )
                expected = (
                    1
                    if model
                    in {
                        ClassCubeAccountRow,
                        ClassCubeCourseRow,
                        ClassCubeCheckinItemRow,
                    }
                    else 0
                )
                self.assertEqual(remaining, expected, model.__name__)
            self.assertIsNotNone(session.get(ClassCubeAccountRow, 2))


class RecordingRepository:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.accounts = {
            1: {
                "id": 1,
                "owner_user_id": 1,
                "name": "账号一",
                "remote_user_name": "甲",
                "cookie": "remember_student_owner=secret",
                "status": "active",
            },
            2: {
                "id": 2,
                "owner_user_id": 2,
                "name": "账号二",
                "remote_user_name": "乙",
                "cookie": "remember_student_other=secret",
                "status": "active",
            },
        }
        self.courses = {
            11: {
                "id": 11,
                "account_id": 1,
                "remote_course_id": "course-a",
                "name": "数据结构",
                "class_code": "A001",
            }
        }
        self.items = {
            21: {
                "id": 21,
                "course_id": 11,
                "remote_item_id": "item-a",
                "title": "签到 A",
                "mode": "gps",
                "remote_module": "punchs",
                "form_action": "https://bjmf.k8n.cn/hidden",
                "form_schema": {"hidden_fields": {"_token": "secret"}},
                "status": "active",
            }
        }
        self.calls = []
        self.next_account_id = 10

    @staticmethod
    def _is_allowed(record, actor_user_id, is_admin):
        return is_admin or record["owner_user_id"] == actor_user_id

    def list_accounts(
        self,
        actor_user_id,
        is_admin,
        owner_user_id=None,
    ):
        self.calls.append(
            (
                "list_accounts",
                actor_user_id,
                is_admin,
                owner_user_id,
            )
        )
        records = list(self.accounts.values())
        if is_admin and owner_user_id is not None:
            records = [
                record
                for record in records
                if record["owner_user_id"] == owner_user_id
            ]
        elif not is_admin:
            records = [
                record
                for record in records
                if record["owner_user_id"] == actor_user_id
            ]
        return [dict(record) for record in records]

    def get_account(self, account_id, actor_user_id, is_admin):
        self.calls.append(
            ("get_account", account_id, actor_user_id, is_admin)
        )
        record = self.accounts.get(account_id)
        if record is None or not self._is_allowed(
            record,
            actor_user_id,
            is_admin,
        ):
            raise ClassCubeNotFound("账号不存在")
        return dict(record)

    def upsert_scanned_account(
        self,
        owner_user_id,
        identity,
        cookie,
        *,
        account_id=None,
        actor_user_id=None,
        is_admin=False,
    ):
        self.events.append(
            (
                "persist_account",
                account_id,
                cookie,
                dict(identity),
            )
        )
        if account_id is None:
            account_id = self.next_account_id
            self.next_account_id += 1
            self.accounts[account_id] = {
                "id": account_id,
                "owner_user_id": owner_user_id,
                "name": (
                    identity.get("remote_user_name")
                    or "班级魔方账号"
                ),
                "remote_user_name": "",
                "cookie": cookie,
                "status": "active",
            }
        else:
            self.get_account(
                account_id,
                actor_user_id,
                is_admin,
            )
        record = self.accounts[account_id]
        record["cookie"] = cookie
        if identity.get("remote_user_name"):
            record["remote_user_name"] = identity[
                "remote_user_name"
            ]
        return dict(record)

    def update_account_name(
        self,
        account_id,
        name,
        actor_user_id,
        is_admin,
    ):
        record = self.get_account(
            account_id,
            actor_user_id,
            is_admin,
        )
        self.accounts[account_id]["name"] = name
        record["name"] = name
        return record

    def delete_account(
        self,
        account_id,
        actor_user_id,
        is_admin,
    ):
        self.get_account(account_id, actor_user_id, is_admin)
        del self.accounts[account_id]

    def get_course(self, course_id, actor_user_id, is_admin):
        self.calls.append(
            ("get_course", course_id, actor_user_id, is_admin)
        )
        record = self.courses.get(course_id)
        if record is None:
            raise ClassCubeNotFound("课程不存在")
        account = self.get_account(
            record["account_id"],
            actor_user_id,
            is_admin,
        )
        if not account:
            raise ClassCubeNotFound("课程不存在")
        return dict(record)

    def list_courses(
        self,
        account_id,
        actor_user_id,
        is_admin,
    ):
        self.get_account(account_id, actor_user_id, is_admin)
        return [
            dict(record)
            for record in self.courses.values()
            if record["account_id"] == account_id
        ]

    def upsert_courses(
        self,
        account_id,
        courses,
        actor_user_id,
        is_admin,
    ):
        self.get_account(account_id, actor_user_id, is_admin)
        courses = list(courses)
        self.events.append(
            (
                "persist_courses",
                account_id,
                [course.remote_course_id for course in courses],
            )
        )
        for course in courses:
            existing = next(
                (
                    value
                    for value in self.courses.values()
                    if value["account_id"] == account_id
                    and value["remote_course_id"]
                    == course.remote_course_id
                ),
                None,
            )
            if existing:
                existing["name"] = course.name
                existing["class_code"] = course.class_code
            else:
                course_id = max(self.courses, default=10) + 1
                self.courses[course_id] = {
                    "id": course_id,
                    "account_id": account_id,
                    "remote_course_id": course.remote_course_id,
                    "name": course.name,
                    "class_code": course.class_code,
                }
        return self.list_courses(
            account_id,
            actor_user_id,
            is_admin,
        )

    def list_items(self, course_id, actor_user_id, is_admin):
        self.get_course(course_id, actor_user_id, is_admin)
        return [
            dict(record)
            for record in self.items.values()
            if record["course_id"] == course_id
        ]

    def upsert_items(
        self,
        course_id,
        bundles,
        actor_user_id,
        is_admin,
    ):
        self.get_course(course_id, actor_user_id, is_admin)
        bundles = list(bundles)
        self.events.append(
            (
                "persist_items",
                course_id,
                [bundle.item.remote_module for bundle in bundles],
            )
        )
        return self.list_items(
            course_id,
            actor_user_id,
            is_admin,
        )


class RecordingClient:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.created = QrSessionView(
            token="qr-token",
            qr_image_base64="cXItYnl0ZXM=",
            expires_at=220.0,
        )
        self.poll_result = QrSessionResult(status="pending")
        self.student_name = "扫码同学"
        self.courses = [
            ParsedCourse("course-a", "数据结构", "A001")
        ]
        self.item_results = {
            "punchs": [],
            "daka": [],
        }

    def create_qr_session(self, owner_user_id):
        self.events.append(("create_qr", owner_user_id))
        return self.created

    def poll_qr_session(self, token, owner_user_id):
        self.events.append(("poll_qr", token, owner_user_id))
        return self.poll_result

    def fetch_student_name(self, cookie):
        self.events.append(("fetch_student_name", cookie))
        if isinstance(self.student_name, BaseException):
            raise self.student_name
        return self.student_name

    def fetch_courses(self, cookie):
        self.events.append(("fetch_courses", cookie))
        if isinstance(self.courses, BaseException):
            raise self.courses
        return list(self.courses)

    def fetch_items(self, cookie, remote_course_id, module="punchs"):
        self.events.append(
            ("fetch_items", cookie, remote_course_id, module)
        )
        result = self.item_results[module]
        if isinstance(result, BaseException):
            raise result
        return list(result)


class RecordingLogger:
    def __init__(self):
        self.records = []

    def warning(self, template, *args):
        self.records.append(template % args)

    def error(self, template, *args):
        self.records.append(template % args)


class ClassCubeServiceTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.repository = RecordingRepository(self.events)
        self.client = RecordingClient(self.events)
        self.logger = RecordingLogger()
        self.service = ClassCubeService(
            self.repository,
            self.client,
            self.logger,
        )
        self.user = {"id": 1, "role": "user"}
        self.admin = {"id": 99, "role": "admin"}

    def test_service_passes_actor_scope_and_admin_owner_filter(self):
        own = self.service.list_accounts(
            self.user,
            owner_user_id=2,
        )
        filtered = self.service.list_accounts(
            self.admin,
            owner_user_id=2,
        )

        self.assertEqual([row["id"] for row in own], [1])
        self.assertEqual([row["id"] for row in filtered], [2])
        self.assertIn(
            ("list_accounts", 1, False, None),
            self.repository.calls,
        )
        self.assertIn(
            ("list_accounts", 99, True, 2),
            self.repository.calls,
        )
        self.assertNotIn("cookie", repr(own))
        self.assertNotIn("secret", repr(filtered))

    def test_rescan_target_is_checked_before_qr_session_creation(self):
        with self.assertRaises(ClassCubeNotFound):
            self.service.create_qr_session(
                self.user,
                account_id=2,
            )

        self.assertNotIn(
            ("create_qr", 1),
            self.events,
        )

    def test_qr_pending_response_is_safe_and_owner_bound(self):
        created = self.service.create_qr_session(self.user)
        result = self.service.poll_qr_session(
            created["token"],
            self.user,
        )

        self.assertTrue(created["qr_image"].startswith("data:image/png;base64,"))
        self.assertEqual(created["expires_in_seconds"], 120)
        self.assertNotIn("expires_at", created)
        self.assertEqual(result, {"status": "pending", "retryable": False})
        self.assertNotIn("cookie", repr(result))
        with self.assertRaises(ClassCubeNotFound):
            self.service.poll_qr_session(
                created["token"],
                {"id": 2, "role": "user"},
            )

    def test_qr_success_persists_cookie_before_identity_and_courses(self):
        self.service.create_qr_session(self.user)
        self.client.poll_result = QrSessionResult(
            status="success",
            cookie="remember_student_scan=top-secret",
        )

        result = self.service.poll_qr_session(
            "qr-token",
            self.user,
        )

        event_names = [event[0] for event in self.events]
        persist_positions = [
            index
            for index, name in enumerate(event_names)
            if name == "persist_account"
        ]
        self.assertLess(
            persist_positions[0],
            event_names.index("fetch_student_name"),
        )
        self.assertLess(
            persist_positions[0],
            event_names.index("fetch_courses"),
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["account"]["remote_user_name"], "扫码同学")
        self.assertEqual(result["courses"][0]["remote_course_id"], "course-a")
        self.assertNotIn("cookie", repr(result))
        self.assertNotIn("top-secret", repr(result))

    def test_qr_success_only_updates_explicit_rescan_target(self):
        self.service.create_qr_session(self.user, account_id=1)
        self.client.poll_result = QrSessionResult(
            status="success",
            cookie="remember_student_scan=updated",
        )

        result = self.service.poll_qr_session(
            "qr-token",
            self.user,
        )

        persisted_targets = [
            event[1]
            for event in self.events
            if event[0] == "persist_account"
        ]
        self.assertEqual(persisted_targets, [1, 1])
        self.assertEqual(result["account"]["id"], 1)
        self.assertEqual(len(self.repository.accounts), 2)

    def test_course_fetch_failure_keeps_account_and_returns_safe_retry_data(self):
        self.service.create_qr_session(self.user)
        self.client.poll_result = QrSessionResult(
            status="success",
            cookie="remember_student_scan=top-secret",
        )
        self.client.courses = ClassCubeRequestError(
            "remote included remember_student_scan=top-secret"
        )

        with self.assertRaises(ClassCubeRemoteError) as captured:
            self.service.poll_qr_session(
                "qr-token",
                self.user,
            )

        error = captured.exception
        self.assertEqual(error.status_code, 502)
        self.assertTrue(error.retryable)
        self.assertEqual(error.data["account"]["id"], 10)
        self.assertIn(10, self.repository.accounts)
        combined = repr((error.message, error.data, self.logger.records))
        self.assertNotIn("top-secret", combined)
        self.assertNotIn("remember_student", combined)

    def test_account_edit_delete_and_course_sync_use_safe_views(self):
        updated = self.service.update_account(
            1,
            {"name": "新的备注"},
            self.user,
        )
        courses = self.service.sync_courses(1, self.user)
        self.service.delete_account(1, self.user)

        self.assertEqual(updated["name"], "新的备注")
        self.assertEqual(courses[0]["remote_course_id"], "course-a")
        self.assertNotIn("cookie", repr(updated))
        self.assertNotIn(1, self.repository.accounts)

    def test_cookie_expiry_is_a_non_retryable_sanitized_remote_error(self):
        self.client.courses = ClassCubeCookieExpired(
            "remember_student_secret=must-not-leak"
        )

        with self.assertRaises(ClassCubeRemoteError) as captured:
            self.service.sync_courses(1, self.user)

        error = captured.exception
        self.assertEqual(error.status_code, 502)
        self.assertFalse(error.retryable)
        self.assertIn("登录已失效", error.message)
        self.assertNotIn(
            "must-not-leak",
            repr((error.message, error.data, self.logger.records)),
        )

    def test_account_note_rejects_blank_value(self):
        with self.assertRaises(ClassCubeValidationError):
            self.service.update_account(
                1,
                {"name": "   "},
                self.user,
            )

    def test_item_sync_keeps_failed_module_cache_when_other_source_succeeds(self):
        self.client.item_results["punchs"] = ClassCubeRequestError(
            "punchs failed with secret"
        )
        self.client.item_results["daka"] = [
            RemoteItemBundle(
                item=ParsedItem(
                    remote_item_id="daka-1",
                    course_id="course-a",
                    title="打卡",
                    remote_module="daka",
                    mode_hint="password",
                ),
                form=ParsedForm(
                    action=(
                        "https://bjmf.k8n.cn/student/"
                        "daka/course/course-a/daka-1"
                    ),
                    method="post",
                    mode="password",
                    hidden_fields={"_token": "hidden"},
                    password_field="code",
                ),
            )
        ]

        items = self.service.sync_items(11, self.user)

        persisted = [
            event
            for event in self.events
            if event[0] == "persist_items"
        ]
        self.assertEqual(persisted, [("persist_items", 11, ["daka"])])
        self.assertEqual(items[0]["id"], 21)
        self.assertNotIn("form_action", repr(items))
        self.assertNotIn("hidden", repr(items))

    def test_item_sync_fails_only_when_both_sources_fail(self):
        self.client.item_results["punchs"] = ClassCubeRequestError(
            "punchs failed"
        )
        self.client.item_results["daka"] = ClassCubeRequestError(
            "daka failed"
        )

        with self.assertRaises(ClassCubeRemoteError) as captured:
            self.service.sync_items(11, self.user)

        self.assertEqual(captured.exception.status_code, 502)
        self.assertTrue(captured.exception.retryable)
        self.assertEqual(
            [
                event
                for event in self.events
                if event[0] == "persist_items"
            ],
            [],
        )


class RouterFakeService:
    def __init__(self):
        self.calls = []
        self.error = None
        self.logger = RecordingLogger()

    def _result(self, name, *args):
        self.calls.append((name, *args))
        if self.error is not None:
            raise self.error
        results = {
            "create_qr_session": {
                "token": "safe-token",
                "qr_image": "data:image/png;base64,cXI=",
                "expires_in_seconds": 120,
            },
            "poll_qr_session": {
                "status": "pending",
                "retryable": False,
            },
            "list_accounts": [{"id": 1, "name": "账号"}],
            "update_account": {"id": 1, "name": "新备注"},
            "delete_account": True,
            "sync_courses": [{"id": 11, "name": "课程"}],
            "list_courses": [{"id": 11, "name": "课程"}],
            "sync_items": [{"id": 21, "title": "签到"}],
            "list_items": [{"id": 21, "title": "签到"}],
        }
        return results[name]

    def create_qr_session(self, actor, account_id=None):
        return self._result(
            "create_qr_session",
            actor,
            account_id,
        )

    def poll_qr_session(self, token, actor):
        return self._result("poll_qr_session", token, actor)

    def list_accounts(self, actor, owner_user_id=None):
        return self._result(
            "list_accounts",
            actor,
            owner_user_id,
        )

    def update_account(self, account_id, payload, actor):
        return self._result(
            "update_account",
            account_id,
            payload,
            actor,
        )

    def delete_account(self, account_id, actor):
        return self._result("delete_account", account_id, actor)

    def sync_courses(self, account_id, actor):
        return self._result("sync_courses", account_id, actor)

    def list_courses(self, account_id, actor):
        return self._result("list_courses", account_id, actor)

    def sync_items(self, course_id, actor):
        return self._result("sync_items", course_id, actor)

    def list_items(self, course_id, actor):
        return self._result("list_items", course_id, actor)


class ClassCubeRouterTest(unittest.TestCase):
    def setUp(self):
        self.service = RouterFakeService()
        app = FastAPI()
        app.state.class_cube_service = self.service

        def current_user():
            return {"id": 7, "role": "admin"}

        self.router = create_class_cube_router(current_user)
        app.include_router(self.router)
        self.app = app
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def test_all_router_endpoints_are_sync_and_use_unified_success_shape(self):
        expected_paths = {
            "/api/class-cube/qr-sessions",
            "/api/class-cube/qr-sessions/{token}",
            "/api/class-cube/accounts",
            "/api/class-cube/accounts/{account_id}",
            "/api/class-cube/accounts/{account_id}/courses/sync",
            "/api/class-cube/accounts/{account_id}/courses",
            "/api/class-cube/courses/{course_id}/items/sync",
            "/api/class-cube/courses/{course_id}/items",
        }
        routes = {
            route.path: route
            for route in self.router.routes
            if isinstance(route, APIRoute)
            and route.path.startswith("/api/class-cube")
        }

        self.assertEqual(set(routes), expected_paths)
        for route in routes.values():
            self.assertFalse(
                inspect.iscoroutinefunction(route.endpoint),
                route.path,
            )

        requests = (
            ("post", "/api/class-cube/qr-sessions", {"json": {}}),
            ("get", "/api/class-cube/qr-sessions/safe-token", {}),
            (
                "get",
                "/api/class-cube/accounts?owner_user_id=2",
                {},
            ),
            (
                "put",
                "/api/class-cube/accounts/1",
                {"json": {"name": "新备注"}},
            ),
            ("delete", "/api/class-cube/accounts/1", {}),
            (
                "post",
                "/api/class-cube/accounts/1/courses/sync",
                {},
            ),
            ("get", "/api/class-cube/accounts/1/courses", {}),
            (
                "post",
                "/api/class-cube/courses/11/items/sync",
                {},
            ),
            ("get", "/api/class-cube/courses/11/items", {}),
        )
        for method, path, kwargs in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(
                    path,
                    **kwargs,
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["ok"])
                self.assertIn("data", response.json())

        self.assertIn(
            (
                "create_qr_session",
                {"id": 7, "role": "admin"},
                None,
            ),
            self.service.calls,
        )
        self.assertIn(
            (
                "list_accounts",
                {"id": 7, "role": "admin"},
                2,
            ),
            self.service.calls,
        )

    def test_router_maps_domain_errors_to_sanitized_statuses(self):
        cases = (
            (
                ClassCubeNotFound("不存在"),
                404,
                "不存在",
                False,
            ),
            (
                ClassCubeValidationError("参数错误"),
                400,
                "参数错误",
                False,
            ),
            (
                ClassCubeRemoteError(
                    "远程服务暂不可用",
                    data={"retryable": True},
                    retryable=True,
                ),
                502,
                "远程服务暂不可用",
                True,
            ),
        )

        for error, status, message, retryable in cases:
            with self.subTest(status=status):
                self.service.error = error
                response = self.client.get(
                    "/api/class-cube/accounts"
                )
                payload = response.json()
                self.assertEqual(response.status_code, status)
                self.assertEqual(payload["ok"], False)
                self.assertEqual(payload["error"], message)
                if status == 502:
                    self.assertEqual(
                        payload["retryable"],
                        retryable,
                    )
                self.assertNotIn("cookie", repr(payload))
                self.service.error = None

    def test_router_sanitizes_unexpected_errors_and_logs_only_type(self):
        self.service.error = RuntimeError(
            "cookie=remember_student_secret; password=123456"
        )

        response = self.client.get("/api/class-cube/accounts")

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(
            payload,
            {
                "ok": False,
                "error": "班级魔方服务内部错误",
            },
        )
        combined = repr(
            (payload, self.service.logger.records)
        )
        self.assertNotIn("remember_student", combined)
        self.assertNotIn("123456", combined)
        self.assertIn("RuntimeError", combined)


class LifecycleFakeBusinessRepository:
    def __init__(self, events):
        self.events = events

    def import_legacy_json_if_empty(self, _path):
        self.events.append("legacy_business")


class LifecycleFakeAppState:
    def __init__(self, events):
        self.events = events
        self.repository = LifecycleFakeBusinessRepository(events)
        self.logger = RecordingLogger()

    def initialize_database(self, _settings):
        self.events.append("business_initialize")

    def start_background_scheduler(self):
        self.events.append("business_scheduler_start")

    def shutdown(self):
        self.events.append("business_shutdown")


class LifecycleFakeAuthService:
    def __init__(self, events):
        self.events = events
        self.repository = None

    def set_repository(self, repository):
        self.events.append("auth_repository_set")
        self.repository = repository


class LifecycleFakeAuthDatabase:
    instances = []

    def __init__(self, _settings):
        self.initialized = False
        self.disposed = False
        self.__class__.instances.append(self)

    def initialize(self):
        self.initialized = True

    def dispose(self):
        self.disposed = True


class LifecycleFakeAuthRepository:
    def __init__(self, _database):
        self.users_initialized = False

    def initialize_users(self, _path):
        self.users_initialized = True


class LifecycleFakeClassCubeDatabase:
    instances = []
    fail_initialize = False

    def __init__(self, _settings):
        self.initialized = False
        self.disposed = False
        self.__class__.instances.append(self)

    def initialize(self):
        self.initialized = True
        if self.__class__.fail_initialize:
            raise RuntimeError(
                "class cube initialize failed with password=123456"
            )

    def dispose(self):
        self.disposed = True


class MainIntegrationTest(unittest.TestCase):
    def setUp(self):
        LifecycleFakeAuthDatabase.instances = []
        LifecycleFakeClassCubeDatabase.instances = []
        LifecycleFakeClassCubeDatabase.fail_initialize = False

    def test_main_mounts_class_cube_api_before_spa_catch_all(self):
        paths = main_module.app.openapi()["paths"]

        self.assertIn("/api/class-cube/accounts", paths)
        self.assertIn("/api/class-cube/qr-sessions", paths)
        routes = list(main_module.app.routes)
        class_cube_index = next(
            index
            for index, route in enumerate(routes)
            if any(
                getattr(child, "path", "").startswith(
                    "/api/class-cube"
                )
                for child in getattr(
                    getattr(route, "original_router", None),
                    "routes",
                    [],
                )
            )
        )
        catch_all_indices = [
            index
            for index, route in enumerate(routes)
            if getattr(route, "path", None)
            == "/{full_path:path}"
        ]
        if catch_all_indices:
            self.assertLess(
                class_cube_index,
                catch_all_indices[0],
            )

    def _lifespan_patches(self, events):
        fake_app_state = LifecycleFakeAppState(events)
        fake_auth_service = LifecycleFakeAuthService(events)
        config = SimpleNamespace(
            business=object(),
            auth=object(),
            class_cube=object(),
        )

        class FakeClassCubeRepository:
            def __init__(self, database):
                self.database = database

        class FakeClassCubeClient:
            pass

        class FakeClassCubeService:
            def __init__(self, repository, client, logger):
                self.repository = repository
                self.client = client
                self.logger = logger

        return (
            fake_app_state,
            fake_auth_service,
            [
                patch.object(
                    main_module,
                    "load_database_config",
                    return_value=config,
                ),
                patch.object(
                    main_module,
                    "app_state",
                    fake_app_state,
                ),
                patch.object(
                    main_module,
                    "auth_service",
                    fake_auth_service,
                ),
                patch.object(
                    main_module,
                    "auth_database",
                    None,
                ),
                patch.object(
                    main_module,
                    "AuthDatabase",
                    LifecycleFakeAuthDatabase,
                ),
                patch.object(
                    main_module,
                    "AuthRepository",
                    LifecycleFakeAuthRepository,
                ),
                patch.object(
                    main_module,
                    "ClassCubeDatabase",
                    LifecycleFakeClassCubeDatabase,
                    create=True,
                ),
                patch.object(
                    main_module,
                    "ClassCubeRepository",
                    FakeClassCubeRepository,
                    create=True,
                ),
                patch.object(
                    main_module,
                    "ClassCubeClient",
                    FakeClassCubeClient,
                    create=True,
                ),
                patch.object(
                    main_module,
                    "ClassCubeService",
                    FakeClassCubeService,
                    create=True,
                ),
            ],
        )

    def test_lifespan_initializes_and_disposes_class_cube_service(self):
        events = []
        (
            fake_app_state,
            _fake_auth_service,
            patches,
        ) = self._lifespan_patches(events)

        async def exercise():
            test_app = FastAPI()
            async with main_module.lifespan(test_app):
                service = test_app.state.class_cube_service
                self.assertIs(
                    service.logger,
                    fake_app_state.logger,
                )
                self.assertTrue(
                    LifecycleFakeClassCubeDatabase.instances[
                        0
                    ].initialized
                )

        with patches[0]:
            with patches[1]:
                with patches[2]:
                    with patches[3]:
                        with patches[4]:
                            with patches[5]:
                                with patches[6]:
                                    with patches[7]:
                                        with patches[8]:
                                            with patches[9]:
                                                asyncio.run(exercise())

        self.assertTrue(
            LifecycleFakeClassCubeDatabase.instances[0].disposed
        )
        self.assertTrue(
            LifecycleFakeAuthDatabase.instances[0].disposed
        )
        self.assertIn("business_shutdown", events)

    def test_lifespan_failure_releases_every_created_resource(self):
        events = []
        LifecycleFakeClassCubeDatabase.fail_initialize = True
        _, _, patches = self._lifespan_patches(events)

        async def exercise():
            test_app = FastAPI()
            async with main_module.lifespan(test_app):
                self.fail("lifespan should not yield")

        with patches[0]:
            with patches[1]:
                with patches[2]:
                    with patches[3]:
                        with patches[4]:
                            with patches[5]:
                                with patches[6]:
                                    with patches[7]:
                                        with patches[8]:
                                            with patches[9]:
                                                with self.assertRaises(
                                                    RuntimeError
                                                ):
                                                    asyncio.run(
                                                        exercise()
                                                    )

        self.assertTrue(
            LifecycleFakeClassCubeDatabase.instances[0].disposed
        )
        self.assertTrue(
            LifecycleFakeAuthDatabase.instances[0].disposed
        )
        self.assertIn("business_shutdown", events)


if __name__ == "__main__":
    unittest.main()
