import threading

import pytest

from app.class_cube_service import ClassCubeService, ClassCubeValidationError


class _Repository:
    def __init__(self):
        self.saved = []

    def get_item(self, item_id, *_):
        return {
            "id": item_id,
            "course_id": 10,
            "remote_item_id": "4508830",
            "remote_module": "punchcard",
            "mode": "qr",
            "title": "签到",
        }

    def get_course(self, *_):
        return {"id": 10, "account_id": 1, "remote_course_id": "course-1", "name": "同一课程"}

    def list_qr_checkin_targets(self, *_):
        return [
            {
                "account": {"id": 1, "owner_user_id": 1, "name": "甲", "status": "active", "cookie": "a"},
                "course": {"id": 10, "account_id": 1, "remote_course_id": "course-1", "name": "同一课程"},
                "item": {"id": 101, "course_id": 10, "remote_item_id": "4508830", "remote_module": "punchcard", "mode": "qr", "title": "签到"},
            },
            {
                "account": {"id": 2, "owner_user_id": 2, "name": "乙", "status": "active", "cookie": "b"},
                "course": {"id": 20, "account_id": 2, "remote_course_id": "course-1", "name": "同一课程"},
                "item": {"id": 202, "course_id": 20, "remote_item_id": "4508830", "remote_module": "punchcard", "mode": "qr", "title": "签到"},
            },
        ]

    def record_manual_run(self, **kwargs):
        self.saved.append(kwargs)


def test_admin_parallel_qr_checkin_runs_targets_concurrently_and_isolates_failure():
    service = ClassCubeService.__new__(ClassCubeService)
    service.repository = _Repository()
    service._record_manual_run = lambda context, summary, started_at: service.repository.record_manual_run(
        context=context,
        summary=summary,
        started_at=started_at,
    )
    barrier = threading.Barrier(2)

    def fake_manual_checkin(item_id, *_args, **_kwargs):
        barrier.wait(timeout=2)
        if item_id == 202:
            raise RuntimeError("one account failed")
        return {"status": "success", "message": "签到成功"}

    service.manual_checkin = fake_manual_checkin
    result = service.admin_parallel_qr_checkin(
        item_id=1,
        qr_url="https://k8n.cn/student/punchw/course/1/4508830?tm=x&sign=y",
        actor={"id": 99, "role": "admin"},
    )

    assert result["total"] == 2
    assert result["success"] == 1
    assert result["failed"] == 1
    assert {row["account_id"] for row in result["details"]} == {1, 2}
    assert len(service.repository.saved) == 2


def test_admin_parallel_qr_checkin_rejects_non_admin_actor():
    service = ClassCubeService.__new__(ClassCubeService)
    service.repository = object()
    service.client = object()

    with pytest.raises(ClassCubeValidationError, match="管理员"):
        service.admin_parallel_qr_checkin(
            item_id=1,
            qr_url="https://k8n.cn/student/punchw/course/1/2?tm=x&sign=y",
            actor={"id": 7, "role": "user"},
        )
