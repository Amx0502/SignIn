import logging
import unittest

from app.class_cube_service import ClassCubeService


class FakeClient:
    def close(self):
        return None


class FakeRepository:
    def __init__(self):
        self.task = {
            "id": 9,
            "owner_user_id": 7,
            "account_id": 1,
            "course_id": 2,
            "name": "立即执行测试",
            "enabled": False,
            "notify_wecom": False,
        }
        self.runs = []

    def get_task(self, task_id, actor_user_id, is_admin):
        return dict(self.task)

    def get_account(self, account_id, actor_user_id, is_admin):
        return {
            "id": 1,
            "owner_user_id": 7,
            "name": "张三",
            "remote_user_name": "张三",
            "cookie": "cookie=value",
            "status": "active",
        }

    def get_course(self, course_id, actor_user_id, is_admin):
        return {"id": 2, "account_id": 1, "name": "高等数学"}

    def record_task_run(
        self, task_id, status, message, response_summary, started_at
    ):
        run = {
            "task_id": task_id,
            "status": status,
            "message": message,
            "response_summary": response_summary,
        }
        self.runs.append(run)
        return run


class ClassCubeExecutionTest(unittest.TestCase):
    def test_manual_disabled_task_returns_no_items_and_records_run(self):
        repository = FakeRepository()
        service = ClassCubeService(
            repository,
            FakeClient(),
            logging.getLogger("execution-test"),
        )
        service.sync_items = lambda course_id, actor: []

        result = service.execute_task(9, trigger="manual")

        self.assertEqual(result["status"], "no_sign_in")
        self.assertEqual(result["scanned"], 0)
        self.assertEqual(repository.runs[0]["status"], "no_sign_in")

    def test_rejects_duplicate_execution_of_same_task(self):
        repository = FakeRepository()
        service = ClassCubeService(
            repository,
            FakeClient(),
            logging.getLogger("execution-lock-test"),
        )
        service._running_task_ids.add(9)

        result = service.execute_task(9, trigger="manual")

        self.assertEqual(result["status"], "running")

    def test_reports_missing_parameters_instead_of_no_pending_items(self):
        repository = FakeRepository()
        repository.try_claim = lambda *args: {
            "id": 3,
            "lease_token": "lease",
            "started_at": None,
        }
        repository.finish_claim = lambda *args, **kwargs: None
        service = ClassCubeService(
            repository,
            FakeClient(),
            logging.getLogger("execution-parameter-test"),
        )
        service.sync_items = lambda course_id, actor: [{
            "id": 4,
            "remote_item_id": "55",
            "remote_module": "punchw",
            "title": "定位签到",
            "mode": "gps_photo",
            "status": "active",
        }]
        service.manual_checkin = lambda *args, **kwargs: {
            "status": "waiting_parameter",
            "message": "请上传签到照片",
        }

        result = service.execute_task(9, trigger="manual")

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(result["message"], "请上传签到照片")
