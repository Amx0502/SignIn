import unittest
from unittest.mock import patch

from app.class_cube_client import ClassCubeClient, ClassCubeRequestError
from app.class_cube_logging import ClassCubeLogStore, create_class_cube_logger
from app.main import app


class _Response:
    def __init__(self, text="<img src='/qr.png'>", url="https://bjmf.k8n.cn/weixin/qrlogin/student", content=b"png"):
        self.text = text
        self.url = url
        self.content = content

    def raise_for_status(self):
        return None


class _RetrySession:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def get(self, url, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("temporary")
        return _Response(content=b"qr")

    def close(self):
        self.closed = True


class ClassCubeIsolationTest(unittest.TestCase):
    def test_bjmf_checklogin_payload_exposes_redirect_url(self):
        status, redirect_url = ClassCubeClient._parse_qr_check_payload(
            {"status": True, "url": "https://bjmf.k8n.cn/weixin/uidlogin/student?x=1"}
        )
        self.assertEqual(status, "success")
        self.assertIn("uidlogin", redirect_url)

    def test_logs_are_split_by_product(self):
        paths = {
            route.path
            for route in app.routes
            if hasattr(route, "path")
        }
        for router in app.routes:
            original = getattr(router, "original_router", None)
            paths.update(
                route.path
                for route in getattr(original, "routes", getattr(router, "routes", []))
                if hasattr(route, "path")
            )
        self.assertIn("/api/xxqd/logs", paths)
        self.assertIn("/api/class-cube/logs", paths)
        self.assertNotIn("/api/logs", paths)

    def test_class_cube_logger_has_an_independent_buffer(self):
        store = ClassCubeLogStore()
        logger = create_class_cube_logger(store)
        logger.info("班级魔方测试")
        self.assertEqual(store.snapshot(), ["班级魔方测试"])

    def test_qr_creation_retries_temporary_remote_failure(self):
        session = _RetrySession()
        client = ClassCubeClient(session_factory=lambda: session)
        with patch("app.class_cube_client.time.sleep"):
            created = client.create_qr_session(1)
        self.assertTrue(created.token)
        self.assertEqual(session.calls, 3)


if __name__ == "__main__":
    unittest.main()
