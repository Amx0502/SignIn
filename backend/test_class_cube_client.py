import base64
import tempfile
import unittest
from pathlib import Path

import requests

from app.class_cube_client import (
    QR_LOGIN_URL,
    ClassCubeClient,
    ClassCubeRequestError,
    QrSessionNotFound,
    RemoteItemBundle,
)
from app.class_cube_parser import (
    ParsedCourse,
    ParsedForm,
    ParsedItem,
    ParsedResult,
)


_MISSING = object()


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        text="",
        content=None,
        url="",
        headers=None,
        json_data=_MISSING,
        cookies=None,
    ):
        self.status_code = status_code
        self.text = text
        self.content = text.encode() if content is None else content
        self.url = url
        self.headers = dict(headers or {})
        self._json_data = json_data
        self.cookies = requests.cookies.cookiejar_from_dict(cookies or {})

    def json(self):
        if self._json_data is _MISSING:
            raise ValueError("response is not JSON")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}",
                response=self,
            )


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = requests.cookies.RequestsCookieJar()
        self.closed = False
        self.uploaded_files = {}

    def get(self, url, **kwargs):
        return self._request("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, kwargs)

    def close(self):
        self.closed = True

    def _request(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        for field_name, file_value in kwargs.get("files", {}).items():
            _, file_object = file_value
            position = file_object.tell()
            self.uploaded_files[field_name] = file_object.read()
            file_object.seek(position)
        if not self.responses:
            raise AssertionError(f"unexpected {method} request to {url}")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if not response.url:
            response.url = url
        return response


class MutableClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def qr_page():
    return FakeResponse(
        text='<img class="qrcode" src="/weixin/qr-code.png">',
        url=QR_LOGIN_URL,
    )


def qr_image():
    return FakeResponse(
        content=b"qr-image-bytes",
        url="https://bjmf.k8n.cn/weixin/qr-code.png",
    )


class ClassCubeQrSessionTest(unittest.TestCase):
    def make_client(self, session, clock=lambda: 100.0):
        return ClassCubeClient(
            session_factory=lambda: session,
            clock=clock,
        )

    def test_qr_session_is_bound_to_owner(self):
        session = FakeSession([qr_page(), qr_image()])
        client = self.make_client(session)

        created = client.create_qr_session(owner_user_id=7)

        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, owner_user_id=8)
        self.assertEqual(len(session.calls), 2)

    def test_qr_session_expires_after_120_seconds(self):
        clock = MutableClock(100.0)
        session = FakeSession([qr_page(), qr_image()])
        client = self.make_client(session, clock)
        created = client.create_qr_session(7)

        clock.value = 221.0

        result = client.poll_qr_session(created.token, 7)
        self.assertEqual(result.status, "expired")
        self.assertTrue(session.closed)
        self.assertEqual(len(session.calls), 2)

    def test_create_qr_session_returns_base64_image(self):
        session = FakeSession([qr_page(), qr_image()])
        client = self.make_client(session)

        created = client.create_qr_session(7)

        self.assertEqual(
            created.qr_image_base64,
            base64.b64encode(b"qr-image-bytes").decode("ascii"),
        )
        self.assertEqual(created.expires_at, 220.0)

    def test_poll_pending_json_keeps_session_open(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(json_data={"status": "pending"}),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "pending")
        self.assertFalse(session.closed)
        self.assertEqual(len(session.calls), 3)

    def test_poll_success_redirect_extracts_remember_student_cookie(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(
                    status_code=302,
                    headers={"Location": "/student"},
                    cookies={
                        "remember_student_abc": "cookie-token",
                        "unrelated": "ignored",
                    },
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.cookie,
            "remember_student_abc=cookie-token",
        )
        self.assertEqual(
            result.redirect_url,
            "https://bjmf.k8n.cn/student",
        )
        self.assertTrue(session.closed)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, 7)

    def test_poll_timeout_is_reported_without_retry_or_cleanup(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                requests.Timeout("slow remote"),
                FakeResponse(
                    status_code=302,
                    headers={"Location": "/student"},
                    cookies={"remember_student_abc": "cookie-token"},
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        first_result = client.poll_qr_session(created.token, 7)

        self.assertEqual(first_result.status, "timeout")
        self.assertFalse(session.closed)
        self.assertEqual(len(session.calls), 3)
        second_result = client.poll_qr_session(created.token, 7)
        self.assertEqual(second_result.status, "success")

    def test_create_cleans_up_expired_sessions(self):
        clock = MutableClock(100.0)
        first_session = FakeSession([qr_page(), qr_image()])
        second_session = FakeSession([qr_page(), qr_image()])
        sessions = iter([first_session, second_session])
        client = ClassCubeClient(
            session_factory=lambda: next(sessions),
            clock=clock,
        )
        first = client.create_qr_session(7)

        clock.value = 221.0
        client.create_qr_session(7)

        self.assertTrue(first_session.closed)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(first.token, 7)

    def test_poll_cleans_up_other_expired_sessions(self):
        clock = MutableClock(100.0)
        first_session = FakeSession([qr_page(), qr_image()])
        second_session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(json_data={"status": "pending"}),
            ]
        )
        sessions = iter([first_session, second_session])
        client = ClassCubeClient(
            session_factory=lambda: next(sessions),
            clock=clock,
        )
        client.create_qr_session(7)
        clock.value = 150.0
        second = client.create_qr_session(7)

        clock.value = 221.0
        result = client.poll_qr_session(second.token, 7)

        self.assertEqual(result.status, "pending")
        self.assertTrue(first_session.closed)
        self.assertFalse(second_session.closed)


class ClassCubeRemoteRequestTest(unittest.TestCase):
    def test_fetch_courses_parses_response_and_injects_request_policy(self):
        session = FakeSession(
            [
                FakeResponse(
                    text=(
                        '<a href="/student/course/101" '
                        'data-class-code="MATH-A">Math</a>'
                    ),
                    url="https://bjmf.k8n.cn/student/courses",
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        courses = client.fetch_courses(
            "remember_student_abc=cookie-token"
        )

        self.assertEqual(
            courses,
            [ParsedCourse("101", "Math", "MATH-A")],
        )
        self.assertTrue(session.closed)
        self.assertEqual(len(session.calls), 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(
            url,
            "https://bjmf.k8n.cn/student/courses",
        )
        self.assertEqual(
            kwargs["headers"]["Cookie"],
            "remember_student_abc=cookie-token",
        )
        self.assertIn(
            "MicroMessenger",
            kwargs["headers"]["User-Agent"],
        )
        self.assertEqual(kwargs["timeout"], (5, 10))

    def test_fetch_courses_has_finite_get_retries(self):
        session = FakeSession(
            [
                requests.Timeout("first"),
                requests.ConnectionError("second"),
                FakeResponse(
                    text='<a href="/student/course/101">Math</a>'
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        courses = client.fetch_courses("cookie=value")

        self.assertEqual(courses, [ParsedCourse("101", "Math")])
        self.assertEqual(len(session.calls), 3)
        self.assertTrue(session.closed)

    def test_fetch_courses_stops_after_three_failed_get_attempts(self):
        session = FakeSession(
            [
                requests.Timeout("first"),
                requests.ConnectionError("second"),
                requests.Timeout("third"),
                FakeResponse(text="must not be requested"),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        with self.assertRaises(ClassCubeRequestError):
            client.fetch_courses("cookie=value")

        self.assertEqual(len(session.calls), 3)
        self.assertTrue(session.closed)

    def test_fetch_items_returns_items_with_their_parsed_forms(self):
        list_url = "https://bjmf.k8n.cn/student/punchs/course/1"
        detail_url = f"{list_url}/12"
        session = FakeSession(
            [
                FakeResponse(
                    text=(
                        '<section id="punchcard_21">'
                        '<form action="/student/punchs/course/1/21" '
                        'method="post">'
                        '<input type="hidden" name="_token" '
                        'value="embedded-token">'
                        "</form></section>"
                        '<a href="/student/punchs/course/1/12" '
                        'data-mode="password">Morning check-in</a>'
                    ),
                    url=list_url,
                ),
                FakeResponse(
                    text=(
                        '<form action="/student/punchs/course/1/12" '
                        'method="post">'
                        '<input type="hidden" name="_token" '
                        'value="detail-token">'
                        '<input type="password" name="passcode">'
                        "</form>"
                    ),
                    url=detail_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        bundles = client.fetch_items("cookie=value", "1")

        self.assertEqual(
            bundles,
            [
                RemoteItemBundle(
                    item=ParsedItem(
                        remote_item_id="21",
                        course_id="1",
                        title="",
                        remote_module="punchs",
                        mode_hint="qr",
                    ),
                    form=ParsedForm(
                        action=(
                            "https://bjmf.k8n.cn/student/"
                            "punchs/course/1/21"
                        ),
                        method="post",
                        mode="qr",
                        hidden_fields={"_token": "embedded-token"},
                    ),
                ),
                RemoteItemBundle(
                    item=ParsedItem(
                        remote_item_id="12",
                        course_id="1",
                        title="Morning check-in",
                        remote_module="punchs",
                        detail_url=detail_url,
                        mode_hint="password",
                    ),
                    form=ParsedForm(
                        action=detail_url,
                        method="post",
                        mode="password",
                        hidden_fields={"_token": "detail-token"},
                        password_field="passcode",
                    ),
                ),
            ],
        )
        self.assertTrue(session.closed)
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("GET", list_url), ("GET", detail_url)],
        )
        for _, _, kwargs in session.calls:
            self.assertEqual(
                kwargs["headers"]["Cookie"],
                "cookie=value",
            )
            self.assertIn(
                "MicroMessenger",
                kwargs["headers"]["User-Agent"],
            )
            self.assertEqual(kwargs["timeout"], (5, 10))

    def test_submit_form_posts_merged_fields_and_parses_result(self):
        result_url = "https://bjmf.k8n.cn/student/punchs/result"
        session = FakeSession(
            [
                FakeResponse(
                    text='<div data-status="success">Done</div>',
                    url=result_url,
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=(
                "https://bjmf.k8n.cn/student/punchs/course/1/12"
            ),
            method="post",
            mode="password",
            hidden_fields={"_token": "token", "course_id": "1"},
            password_field="passcode",
        )

        result = client.submit_form(
            "remember_student_abc=cookie-token",
            form,
            {"passcode": "1234", "course_id": "override"},
        )

        self.assertEqual(
            result,
            ParsedResult(
                status="success",
                message="Done",
                response_url=result_url,
            ),
        )
        self.assertTrue(session.closed)
        self.assertEqual(len(session.calls), 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, form.action)
        self.assertEqual(
            kwargs["data"],
            {
                "_token": "token",
                "course_id": "override",
                "passcode": "1234",
            },
        )
        self.assertEqual(
            kwargs["headers"]["Cookie"],
            "remember_student_abc=cookie-token",
        )
        self.assertIn(
            "MicroMessenger",
            kwargs["headers"]["User-Agent"],
        )
        self.assertEqual(kwargs["timeout"], (5, 10))

    def test_submit_post_does_not_retry_after_timeout(self):
        session = FakeSession(
            [
                requests.Timeout("submission timed out"),
                FakeResponse(
                    text='<div data-status="success">Must not run</div>'
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=(
                "https://bjmf.k8n.cn/student/punchs/course/1/12"
            ),
            method="post",
            mode="password",
            hidden_fields={"_token": "token"},
        )

        with self.assertRaises(ClassCubeRequestError):
            client.submit_form("cookie=value", form, {})

        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.closed)

    def test_submit_get_uses_params_and_finite_get_retries(self):
        session = FakeSession(
            [
                requests.Timeout("first"),
                FakeResponse(
                    text='<div data-status="success">Done</div>',
                    url=(
                        "https://bjmf.k8n.cn/student/punchs/result"
                    ),
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=(
                "https://bjmf.k8n.cn/student/punchs/course/1/12"
            ),
            method="get",
            mode="qr",
            hidden_fields={"_token": "token"},
        )

        result = client.submit_form(
            "cookie=value",
            form,
            {"code": "1234"},
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(len(session.calls), 2)
        for method, url, kwargs in session.calls:
            self.assertEqual(method, "GET")
            self.assertEqual(url, form.action)
            self.assertEqual(
                kwargs["params"],
                {"_token": "token", "code": "1234"},
            )
            self.assertNotIn("data", kwargs)
        self.assertTrue(session.closed)

    def test_submit_form_uploads_photo_with_declared_file_field(self):
        session = FakeSession(
            [
                FakeResponse(
                    text='<div data-status="success">Uploaded</div>'
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=(
                "https://bjmf.k8n.cn/student/punch_gps/course/1/12"
            ),
            method="post",
            mode="gps_photo",
            hidden_fields={"_token": "token"},
            file_field="proof",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            photo_path = Path(temp_dir) / "proof.jpg"
            photo_path.write_bytes(b"photo-bytes")

            result = client.submit_form(
                "cookie=value",
                form,
                {"lat": "39.9", "lng": "116.4"},
                photo_path=photo_path,
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(
            session.uploaded_files,
            {"proof": b"photo-bytes"},
        )
        _, _, kwargs = session.calls[0]
        file_name, file_object = kwargs["files"]["proof"]
        self.assertEqual(file_name, "proof.jpg")
        self.assertTrue(file_object.closed)
        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
