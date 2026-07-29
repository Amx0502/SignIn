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
                "success": 1,
                "failed": 0,
                "details": ["签到成功"],
            },
        )
        self.assertEqual(
            http.posts[0][1]["json"]["msgtype"],
            "markdown",
        )

    def test_rejects_remote_error(self):
        with self.assertRaises(ClassCubeNotificationError):
            ClassCubeNotifier(FakeHttp({"errcode": 93000})).send_summary(
                WEBHOOK, {"task_name": "高数"}
            )

