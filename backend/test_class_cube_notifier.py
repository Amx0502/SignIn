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
                "failed": 1,
                "already_signed": 1,
                "skipped": 0,
                "unknown": 1,
                "parameters": {
                    "longitude": "119.3800000",
                    "latitude": "26.0900000",
                    "image_count": 1,
                    "password": "123456",
                },
                "details": [
                    {
                        "title": "课堂定位",
                        "mode": "gps",
                        "status": "success",
                        "message": "签到成功",
                        "executed_at": "10:55:50",
                    },
                    {
                        "title": "课前签到",
                        "mode": "qr",
                        "status": "already_signed",
                        "message": "已经完成",
                        "executed_at": "10:55:51",
                    },
                ],
            },
        )
        self.assertEqual(
            http.posts[0][1]["json"]["msgtype"],
            "markdown",
        )
        content = http.posts[0][1]["json"]["markdown"]["content"]
        self.assertIn("📊 班级魔方通知汇总", content)
        self.assertIn("时间：2026-07-30 10:50", content)
        self.assertIn("课程：高等数学", content)
        self.assertIn("手动立即执行", content)
        self.assertIn("成功：2 个｜失败：2 个", content)
        self.assertIn("张三 [10:55:50]", content)
        self.assertIn("📍位置：119.38, 26.09", content)
        self.assertIn("🖼️图片：1张", content)
        self.assertIn("🔑密码：123456", content)
        self.assertIn("类型：GPS 签到", content)
        self.assertIn("已完成，无需重复签到", content)
        self.assertNotIn("任务：高数", content)
        self.assertNotIn("课堂定位", content)
        self.assertNotIn("课前签到", content)
        self.assertNotIn("已完成：", content)
        self.assertNotIn("already_signed", content)

    def test_omits_unconfigured_coordinates_and_password(self):
        http = FakeHttp({"errcode": 0})
        ClassCubeNotifier(http).send_summary(
            WEBHOOK,
            {
                "parameters": {
                    "longitude": None,
                    "latitude": None,
                    "image_count": 0,
                    "password": "",
                },
                "details": [],
            },
        )

        content = http.posts[0][1]["json"]["markdown"]["content"]
        self.assertNotIn("📍位置", content)
        self.assertNotIn("🖼️图片", content)
        self.assertNotIn("🔑密码", content)

    def test_omits_invalid_coordinates_without_failing_notification(self):
        http = FakeHttp({"errcode": 0})
        ClassCubeNotifier(http).send_summary(
            WEBHOOK,
            {
                "parameters": {
                    "longitude": "invalid",
                    "latitude": "26.09",
                    "image_count": 0,
                    "password": "",
                },
                "details": [],
            },
        )

        content = http.posts[0][1]["json"]["markdown"]["content"]
        self.assertNotIn("📍位置", content)

    def test_rejects_remote_error(self):
        with self.assertRaises(ClassCubeNotificationError):
            ClassCubeNotifier(FakeHttp({"errcode": 93000})).send_summary(
                WEBHOOK, {"task_name": "高数"}
            )
