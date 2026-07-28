import threading
import time
import unittest
import inspect
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.class_cube_database import ClassCubeDatabase
from app.class_cube_db_models import (
    ClassCubeAccountRow,
    ClassCubeBase,
    ClassCubeCheckinItemRow,
    ClassCubeCourseRow,
    ClassCubeTaskItemClaimRow,
    ClassCubeTaskRow,
)
from app.class_cube_models import ClassCubeTaskCreate, task_view
from app.class_cube_repository import ClassCubeNotFound, ClassCubeRepository
from app.class_cube_scheduler import ClassCubeScheduler


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeService:
    def __init__(self):
        self.scan_calls = []
        self.tasks = [{"id": 1}, {"id": 2}, {"id": 3}]
        self.block = None
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()

    def list_due_tasks(self):
        return self.tasks

    def run_scheduled_task(self, task_id):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        self.scan_calls.append(task_id)
        if self.block:
            self.block.wait(1)
        with self.lock:
            self.active -= 1


class SchedulerTests(unittest.TestCase):
    def test_interval_is_exactly_thirty_seconds(self):
        clock = FakeClock()
        service = FakeService()
        service.tasks = [{"id": 1}]
        scheduler = ClassCubeScheduler(
            service, clock=clock, start_thread=False, max_workers=1
        )
        scheduler.tick()
        scheduler.wait_for_idle()
        clock.advance(29.999)
        scheduler.tick()
        scheduler.wait_for_idle()
        self.assertEqual(service.scan_calls, [1])
        clock.advance(0.001)
        scheduler.tick()
        scheduler.wait_for_idle()
        self.assertEqual(service.scan_calls, [1, 1])
        scheduler.shutdown()

    def test_clock_rollback_does_not_postpone_next_scan_forever(self):
        clock = FakeClock()
        service = FakeService()
        service.tasks = [{"id": 1}]
        scheduler = ClassCubeScheduler(
            service, clock=clock, start_thread=False, max_workers=1
        )
        scheduler.tick()
        scheduler.wait_for_idle()
        clock.value = 10
        scheduler.tick()
        clock.advance(30)
        scheduler.tick()
        scheduler.wait_for_idle()
        self.assertEqual(service.scan_calls, [1, 1])
        scheduler.shutdown()

    def test_shared_submit_prevents_reentry_and_limits_workers(self):
        service = FakeService()
        service.block = threading.Event()
        scheduler = ClassCubeScheduler(
            service, start_thread=False, max_workers=99
        )
        self.assertTrue(scheduler.submit(1))
        self.assertFalse(scheduler.submit(1))
        self.assertTrue(scheduler.submit(2))
        self.assertTrue(scheduler.submit(3))
        time.sleep(0.05)
        self.assertLessEqual(service.maximum, 2)
        service.block.set()
        scheduler.wait_for_idle()
        self.assertTrue(scheduler.submit(1))
        service.block.set()
        scheduler.wait_for_idle()
        scheduler.shutdown()
        scheduler.shutdown()


class ContractTests(unittest.TestCase):
    def test_task_password_is_write_only(self):
        model = ClassCubeTaskCreate(
            account_id=1, course_id=2, name="任务", password="secret"
        )
        self.assertEqual(model.poll_interval_seconds, 30)
        view = task_view(
            {"id": 1, "password": "secret", "poll_interval_seconds": 30}
        )
        self.assertNotIn("password", view)
        self.assertTrue(view["has_password"])

    def test_claim_identity_includes_remote_module_and_lease(self):
        unique_columns = {
            column.name
            for constraint in ClassCubeTaskItemClaimRow.__table__.constraints
            if getattr(constraint, "name", "") == "uq_class_cube_claims_task_remote"
            for column in constraint.columns
        }
        self.assertEqual(
            unique_columns,
            {"task_id", "remote_module", "remote_item_id"},
        )
        self.assertIn("lease_until", ClassCubeTaskItemClaimRow.__table__.columns)

    def test_database_uses_small_pool(self):
        source = inspect.getsource(ClassCubeDatabase.initialize)
        self.assertIn("pool_size=2", source)
        self.assertIn("max_overflow=0", source)
        self.assertIn("poolclass=NullPool", source)


class MemoryDatabase:
    def __init__(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ClassCubeBase.metadata.create_all(self.engine)
        self.factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, autoflush=False
        )

    @contextmanager
    def session(self):
        session = self.factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.database = MemoryDatabase()
        self.repository = ClassCubeRepository(self.database)
        with self.database.session() as session:
            session.add_all(
                [
                    ClassCubeAccountRow(
                        id=1, owner_user_id=7, name="a",
                        remote_user_name="a", cookie="secret",
                        status="active",
                    ),
                    ClassCubeAccountRow(
                        id=2, owner_user_id=8, name="b",
                        remote_user_name="b", cookie="secret2",
                        status="active",
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    ClassCubeCourseRow(
                        id=11, account_id=1, remote_course_id="c1",
                        name="course", payload={},
                    ),
                    ClassCubeCourseRow(
                        id=12, account_id=2, remote_course_id="c2",
                        name="course2", payload={},
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    ClassCubeCheckinItemRow(
                        id=21, course_id=11, remote_item_id="same",
                        remote_module="punchs", title="p", mode="qr",
                        form_schema={}, status="active",
                    ),
                    ClassCubeCheckinItemRow(
                        id=22, course_id=11, remote_item_id="same",
                        remote_module="daka", title="d", mode="qr",
                        form_schema={}, status="active",
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    ClassCubeTaskRow(
                        id=31, owner_user_id=7, account_id=1,
                        course_id=11, name="t", enabled=True,
                    ),
                    ClassCubeTaskRow(
                        id=32, owner_user_id=8, account_id=2,
                        course_id=12, name="other", enabled=True,
                    ),
                ]
            )

    def tearDown(self):
        self.database.engine.dispose()

    def test_claims_same_remote_id_in_different_modules(self):
        first = self.repository.try_claim(31, 21, "same", "punchs")
        second = self.repository.try_claim(31, 22, "same", "daka")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)

    def test_retryable_and_expired_lease_can_be_reclaimed(self):
        claim = self.repository.try_claim(31, 21, "same", "punchs")
        self.repository.finish_claim(
            claim["id"], 31, 21, "same", "punchs",
            "retryable", "waiting_parameter",
        )
        self.assertIsNotNone(
            self.repository.try_claim(31, 21, "same", "punchs")
        )
        with self.database.session() as session:
            row = session.get(ClassCubeTaskItemClaimRow, claim["id"])
            row.lease_until = datetime.now() - timedelta(seconds=1)
        self.assertIsNotNone(
            self.repository.try_claim(31, 21, "same", "punchs")
        )

    def test_unknown_requires_explicit_confirmation(self):
        claim = self.repository.try_claim(31, 21, "same", "punchs")
        self.repository.finish_claim(
            claim["id"], 31, 21, "same", "punchs",
            "unknown", "unknown_result",
        )
        self.assertIsNone(
            self.repository.try_claim(31, 21, "same", "punchs")
        )
        self.assertTrue(
            self.repository.confirm_claim_retry(claim["id"], 7, False)
        )
        self.assertIsNotNone(
            self.repository.try_claim(31, 21, "same", "punchs")
        )

    def test_batch_delete_is_all_or_nothing_for_owner(self):
        with self.assertRaises(ClassCubeNotFound):
            self.repository.delete_tasks([31, 32], 7, False)
        self.assertEqual(
            [task["id"] for task in self.repository.list_tasks(7, False)],
            [31],
        )

    def test_expiring_account_disables_tasks_in_same_transaction(self):
        self.repository.mark_account_expired(1, 7, False)
        task = self.repository.get_task(31, 7, False)
        self.assertFalse(task["enabled"])


if __name__ == "__main__":
    unittest.main()
