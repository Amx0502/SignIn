import unittest

from app.class_cube_notifier import (
    ClassCubeNotificationError,
    ClassCubeNotifier,
)


WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse(self.payload)


class ClassCubeNotifierTest(unittest.TestCase):
    def test_posts_markdown_summary(self):
        http = FakeHttp({"errcode": 0})
        ClassCubeNotifier(http).send_summary(
            WEBHOOK,
            {
                "task_name": "高数",
                "account_name": "张三",
                "course_name": "高等数学",
                "status": "success",
                "trigger": "manual",
                "started_at": "2026-07-30 10:50:00",
                "scanned": 2,
                "success": 1,
                "failed": 0,
                "already_signed": 1,
                "skipped": 0,
                "unknown": 0,
                "details": [
                    {
                        "title": "课堂定位",
                        "mode": "gps",
                        "status": "success",
                        "message": "签到成功",
                    },
                    {
                        "title": "课前签到",
                        "mode": "qr",
                        "status": "already_signed",
                        "message": "已经完成",
                    },
                ],
            },
        )
        self.assertEqual(
            http.posts[0][1]["json"]["msgtype"],
            "markdown",
        )
        content = http.posts[0][1]["json"]["markdown"]["content"]
        self.assertIn("✅ 班级魔方签到成功", content)
        self.assertIn("手动立即执行", content)
        self.assertIn("GPS 签到", content)
        self.assertIn("已完成，无需重复签到", content)
        self.assertIn("2026-07-30 10:50:00", content)
        self.assertNotIn("already_signed", content)

    def test_rejects_remote_error(self):
        with self.assertRaises(ClassCubeNotificationError):
            ClassCubeNotifier(FakeHttp({"errcode": 93000})).send_summary(
                WEBHOOK, {"task_name": "高数"}
            )
