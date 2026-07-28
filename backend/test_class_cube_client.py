import base64
import tempfile
import threading
import unittest
from pathlib import Path

import requests

from app.class_cube_client import (
    QR_LOGIN_URL,
    ClassCubeClient,
    ClassCubeCookieExpired,
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


class ExplodingJsonResponse(FakeResponse):
    def json(self):
        raise RuntimeError("malformed remote JSON")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = requests.cookies.RequestsCookieJar()
        self.closed = False
        self.close_calls = 0
        self.uploaded_files = {}

    def get(self, url, **kwargs):
        return self._request("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, kwargs)

    def close(self):
        self.close_calls += 1
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
        if callable(response):
            response = response()
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

    def test_qr_ttl_starts_after_image_download_succeeds(self):
        clock = MutableClock(100.0)

        def delayed_image():
            clock.value = 180.0
            return qr_image()

        session = FakeSession(
            [
                qr_page(),
                delayed_image,
                FakeResponse(json_data={"status": "pending"}),
            ]
        )
        client = self.make_client(session, clock)

        created = client.create_qr_session(7)

        self.assertEqual(created.expires_at, 300.0)
        clock.value = 299.0
        result = client.poll_qr_session(created.token, 7)
        self.assertEqual(result.status, "pending")
        self.assertFalse(session.closed)

    def test_success_response_finishing_after_ttl_is_expired(self):
        clock = MutableClock(100.0)

        def delayed_success():
            clock.value = 221.0
            return FakeResponse(
                status_code=302,
                headers={
                    "Location": "/weixin/uidlogin/student",
                },
                cookies={"remember_student_abc": "cookie-token"},
            )

        session = FakeSession(
            [qr_page(), qr_image(), delayed_success]
        )
        client = self.make_client(session, clock)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "expired")
        self.assertEqual(result.cookie, "")
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)

    def test_expired_in_flight_session_is_removed_then_closed_on_finish(self):
        clock = MutableClock(100.0)
        request_started = threading.Event()
        release_request = threading.Event()

        def blocking_success():
            request_started.set()
            if not release_request.wait(2):
                raise AssertionError("test did not release remote request")
            return FakeResponse(
                status_code=302,
                headers={
                    "Location": "/weixin/uidlogin/student",
                },
                cookies={"remember_student_abc": "cookie-token"},
            )

        session = FakeSession(
            [qr_page(), qr_image(), blocking_success]
        )
        client = self.make_client(session, clock)
        created = client.create_qr_session(7)
        first_results = []
        first_errors = []

        def first_poll():
            try:
                first_results.append(
                    client.poll_qr_session(created.token, 7)
                )
            except BaseException as exc:
                first_errors.append(exc)

        first = threading.Thread(target=first_poll)
        first.start()
        self.assertTrue(request_started.wait(1))
        clock.value = 221.0

        second_result = client.poll_qr_session(created.token, 7)
        closed_before_release = session.closed
        try:
            client.poll_qr_session(created.token, 7)
        except QrSessionNotFound:
            removed_before_release = True
        else:
            removed_before_release = False
        release_request.set()
        first.join(2)

        self.assertEqual(second_result.status, "expired")
        self.assertTrue(removed_before_release)
        self.assertFalse(closed_before_release)
        self.assertFalse(first.is_alive())
        self.assertEqual(first_errors, [])
        self.assertEqual(len(first_results), 1)
        self.assertEqual(first_results[0].status, "expired")
        self.assertEqual(first_results[0].cookie, "")
        self.assertTrue(session.closed)
        self.assertEqual(len(session.calls), 3)

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
                    headers={
                        "Location": "/weixin/uidlogin/student",
                    },
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
            "https://bjmf.k8n.cn/weixin/uidlogin/student",
        )
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, 7)

    def test_poll_timeout_is_retryable_error_without_cleanup(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                requests.Timeout("slow remote"),
                FakeResponse(
                    status_code=302,
                    headers={
                        "Location": "/weixin/uidlogin/student",
                    },
                    cookies={"remember_student_abc": "cookie-token"},
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        first_result = client.poll_qr_session(created.token, 7)

        self.assertEqual(first_result.status, "error")
        self.assertTrue(first_result.retryable)
        self.assertFalse(session.closed)
        self.assertEqual(len(session.calls), 3)
        second_result = client.poll_qr_session(created.token, 7)
        self.assertEqual(second_result.status, "success")

    def test_poll_http_error_is_retryable_and_keeps_session(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(status_code=503),
                FakeResponse(
                    status_code=302,
                    headers={
                        "Location": "/weixin/uidlogin/student",
                    },
                    cookies={"remember_student_abc": "cookie-token"},
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        first_result = client.poll_qr_session(created.token, 7)

        self.assertEqual(first_result.status, "error")
        self.assertTrue(first_result.retryable)
        self.assertFalse(session.closed)
        second_result = client.poll_qr_session(created.token, 7)
        self.assertEqual(second_result.status, "success")

    def test_poll_permanent_http_error_is_terminal(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(status_code=400),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "error")
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, 7)

    def test_poll_terminal_json_error_is_not_retryable_and_cleans_up(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(json_data={"status": "failed"}),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "error")
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, 7)

    def test_poll_ordinary_redirect_is_terminal_error_even_with_cookie(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(
                    status_code=302,
                    headers={"Location": "/student"},
                    cookies={"remember_student_abc": "cookie-token"},
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "error")
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)

    def test_poll_expected_redirect_without_cookie_is_terminal_error(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(
                    status_code=302,
                    headers={
                        "Location": "/weixin/uidlogin/student",
                    },
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        result = client.poll_qr_session(created.token, 7)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.cookie, "")
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)

    def test_poll_explicit_success_requires_and_returns_cookie(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                FakeResponse(
                    json_data={"status": "success"},
                    cookies={"remember_student_abc": "cookie-token"},
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
        self.assertFalse(result.retryable)
        self.assertTrue(session.closed)

    def test_poll_parse_exception_releases_in_flight_for_retry(self):
        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                ExplodingJsonResponse(),
                FakeResponse(
                    status_code=302,
                    headers={
                        "Location": "/weixin/uidlogin/student",
                    },
                    cookies={"remember_student_abc": "cookie-token"},
                ),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)

        first_result = client.poll_qr_session(created.token, 7)

        self.assertEqual(first_result.status, "error")
        self.assertTrue(first_result.retryable)
        self.assertFalse(session.closed)
        second_result = client.poll_qr_session(created.token, 7)
        self.assertEqual(second_result.status, "success")
        self.assertTrue(session.closed)
        self.assertEqual(len(session.calls), 4)

    def test_concurrent_poll_returns_pending_while_first_is_in_flight(self):
        request_started = threading.Event()
        release_request = threading.Event()

        def blocking_pending_response():
            request_started.set()
            if not release_request.wait(2):
                raise AssertionError("test did not release remote request")
            return FakeResponse(json_data={"status": "pending"})

        session = FakeSession(
            [
                qr_page(),
                qr_image(),
                blocking_pending_response,
                FakeResponse(json_data={"status": "pending"}),
            ]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)
        results = {}
        errors = []

        def poll(name):
            try:
                results[name] = client.poll_qr_session(
                    created.token,
                    7,
                )
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=poll, args=("first",))
        second = threading.Thread(target=poll, args=("second",))
        first.start()
        self.assertTrue(request_started.wait(1))
        second.start()
        second.join(0.2)
        second_finished_without_remote = not second.is_alive()
        release_request.set()
        first.join(2)
        second.join(2)

        self.assertTrue(second_finished_without_remote)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(results["first"].status, "pending")
        self.assertEqual(results["second"].status, "pending")
        self.assertEqual(len(session.calls), 3)

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

    def test_cancel_qr_session_closes_pending_session_once(self):
        session = FakeSession([qr_page(), qr_image()])
        client = self.make_client(session)
        created = client.create_qr_session(7)

        first = client.cancel_qr_session(created.token, 7)
        second = client.cancel_qr_session(created.token, 7)
        client.close()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(session.closed)
        self.assertEqual(session.close_calls, 1)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(created.token, 7)

    def test_cancel_in_flight_session_defers_close_until_poll_finishes(self):
        request_started = threading.Event()
        release_request = threading.Event()

        def blocking_pending():
            request_started.set()
            if not release_request.wait(2):
                raise AssertionError("test did not release remote request")
            return FakeResponse(json_data={"status": "pending"})

        session = FakeSession(
            [qr_page(), qr_image(), blocking_pending]
        )
        client = self.make_client(session)
        created = client.create_qr_session(7)
        results = []

        worker = threading.Thread(
            target=lambda: results.append(
                client.poll_qr_session(created.token, 7)
            )
        )
        worker.start()
        self.assertTrue(request_started.wait(1))

        cancelled = client.cancel_qr_session(created.token, 7)
        closed_before_release = session.closed
        release_request.set()
        worker.join(2)

        self.assertTrue(cancelled)
        self.assertFalse(closed_before_release)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].status, "expired")
        self.assertTrue(session.closed)
        self.assertEqual(session.close_calls, 1)

    def test_close_cancels_all_sessions_and_is_idempotent(self):
        first_session = FakeSession([qr_page(), qr_image()])
        second_session = FakeSession([qr_page(), qr_image()])
        sessions = iter([first_session, second_session])
        client = ClassCubeClient(
            session_factory=lambda: next(sessions),
            clock=lambda: 100.0,
        )
        first = client.create_qr_session(7)
        second = client.create_qr_session(8)

        client.close()
        client.close()

        self.assertTrue(first_session.closed)
        self.assertTrue(second_session.closed)
        self.assertEqual(first_session.close_calls, 1)
        self.assertEqual(second_session.close_calls, 1)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(first.token, 7)
        with self.assertRaises(QrSessionNotFound):
            client.poll_qr_session(second.token, 8)


class ClassCubeRemoteRequestTest(unittest.TestCase):
    def test_fetch_student_name_uses_authenticated_profile_page(self):
        profile_url = "https://bjmf.k8n.cn/student/my"
        session = FakeSession(
            [
                FakeResponse(
                    text=(
                        "<script>var gconfig={uid:'7',"
                        "uname:'扫码同学'};</script>"
                    ),
                    url=profile_url,
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        name = client.fetch_student_name(
            "remember_student_abc=cookie-token"
        )

        self.assertEqual(name, "扫码同学")
        self.assertTrue(session.closed)
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("GET", profile_url)],
        )
        _, _, kwargs = session.calls[0]
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertEqual(
            [
                (cookie.name, cookie.value, cookie.domain)
                for cookie in session.cookies
            ],
            [
                (
                    "remember_student_abc",
                    "cookie-token",
                    ".k8n.cn",
                )
            ],
        )

    def test_authenticated_readers_reject_login_page_as_cookie_expired(self):
        login_html = (
            '<form action="/student/login">'
            '<input type="password" name="password">'
            "</form>"
        )
        cases = (
            (
                "profile",
                lambda client: client.fetch_student_name(
                    "cookie=value"
                ),
                [
                    FakeResponse(
                        text=login_html,
                        url="https://bjmf.k8n.cn/student/login",
                    )
                ],
                1,
            ),
            (
                "courses",
                lambda client: client.fetch_courses("cookie=value"),
                [
                    FakeResponse(
                        text=login_html,
                        url="https://bjmf.k8n.cn/student/login",
                    )
                ],
                1,
            ),
            (
                "item-list",
                lambda client: client.fetch_items(
                    "cookie=value",
                    "1",
                ),
                [
                    FakeResponse(
                        text=login_html,
                        url="https://bjmf.k8n.cn/student/login",
                    )
                ],
                1,
            ),
            (
                "item-detail",
                lambda client: client.fetch_items(
                    "cookie=value",
                    "1",
                ),
                [
                    FakeResponse(
                        text=(
                            '<a href="/student/punchs/course/1/12">'
                            "签到</a>"
                        ),
                        url=(
                            "https://bjmf.k8n.cn/student/"
                            "punchs/course/1"
                        ),
                    ),
                    FakeResponse(
                        text=login_html,
                        url="https://bjmf.k8n.cn/student/login",
                    ),
                ],
                2,
            ),
        )

        for name, invoke, responses, expected_calls in cases:
            with self.subTest(name):
                session = FakeSession(responses)
                client = ClassCubeClient(
                    session_factory=lambda: session
                )

                with self.assertRaises(ClassCubeCookieExpired):
                    invoke(client)

                self.assertEqual(
                    len(session.calls),
                    expected_calls,
                )
                self.assertTrue(session.closed)

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
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertEqual(
            [
                (cookie.name, cookie.value, cookie.domain)
                for cookie in session.cookies
            ],
            [
                (
                    "remember_student_abc",
                    "cookie-token",
                    ".k8n.cn",
                )
            ],
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
            self.assertNotIn("Cookie", kwargs["headers"])
            self.assertIn(
                "MicroMessenger",
                kwargs["headers"]["User-Agent"],
            )
            self.assertEqual(kwargs["timeout"], (5, 10))
        self.assertEqual(
            [
                (cookie.name, cookie.value, cookie.domain)
                for cookie in session.cookies
            ],
            [("cookie", "value", ".k8n.cn")],
        )

    def test_fetch_items_supports_daka_as_an_explicit_list_source(self):
        list_url = "https://bjmf.k8n.cn/student/daka/course/1"
        session = FakeSession(
            [
                FakeResponse(
                    text=(
                        '<form id="punchcard_88" '
                        'action="/student/daka/course/1/88" '
                        'method="post">'
                        '<input type="hidden" name="_token" value="safe">'
                        "</form>"
                    ),
                    url=list_url,
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        bundles = client.fetch_items(
            "cookie=value",
            "1",
            module="daka",
        )

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].item.remote_module, "daka")
        self.assertEqual(bundles[0].item.remote_item_id, "88")
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("GET", list_url)],
        )

    def test_fetch_items_rejects_unapproved_list_module_before_request(self):
        session = FakeSession([])
        client = ClassCubeClient(session_factory=lambda: session)

        with self.assertRaises(ValueError):
            client.fetch_items(
                "cookie=value",
                "1",
                module="../../evil",
            )

        self.assertEqual(session.calls, [])
        self.assertTrue(session.closed)

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
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertIn(
            "MicroMessenger",
            kwargs["headers"]["User-Agent"],
        )
        self.assertEqual(kwargs["timeout"], (5, 10))
        self.assertEqual(
            [
                (cookie.name, cookie.value, cookie.domain)
                for cookie in session.cookies
            ],
            [
                (
                    "remember_student_abc",
                    "cookie-token",
                    ".k8n.cn",
                )
            ],
        )

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

    def test_fetch_items_rejects_untrusted_detail_url_before_request(self):
        list_url = "https://bjmf.k8n.cn/student/punchs/course/1"
        malicious_url = (
            "https://evil.example/student/punchs/course/1/12"
        )
        session = FakeSession(
            [
                FakeResponse(
                    text=(
                        f'<a href="{malicious_url}">'
                        "Untrusted check-in</a>"
                    ),
                    url=list_url,
                ),
                FakeResponse(
                    text='<form method="post"></form>',
                    url=malicious_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        with self.assertRaises(ClassCubeRequestError):
            client.fetch_items(
                "remember_student_abc=cookie-token",
                "1",
            )

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][1], list_url)
        self.assertNotIn("Cookie", session.calls[0][2]["headers"])
        self.assertTrue(session.closed)

    def test_submit_form_rejects_untrusted_action_before_request(self):
        actions = [
            "https://evil.example/student/punchs/course/1/12",
            "http://bjmf.k8n.cn/student/punchs/course/1/12",
        ]
        for action in actions:
            with self.subTest(action):
                session = FakeSession(
                    [
                        FakeResponse(
                            text=(
                                '<div data-status="success">Done</div>'
                            )
                        )
                    ]
                )
                client = ClassCubeClient(
                    session_factory=lambda: session
                )
                form = ParsedForm(
                    action=action,
                    method="post",
                    mode="password",
                    hidden_fields={"_token": "token"},
                )

                with self.assertRaises(ClassCubeRequestError):
                    client.submit_form(
                        "remember_student_abc=cookie-token",
                        form,
                        {},
                    )

                self.assertEqual(session.calls, [])

    def test_fetch_courses_rejects_untrusted_redirect_before_next_get(self):
        first_url = "https://bjmf.k8n.cn/student/courses"
        malicious_url = "https://evil.k8n.cn/student/courses"
        session = FakeSession(
            [
                FakeResponse(
                    status_code=302,
                    headers={"Location": malicious_url},
                    url=first_url,
                ),
                FakeResponse(
                    text='<a href="/student/course/1">Leaked</a>',
                    url=malicious_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        with self.assertRaises(ClassCubeRequestError):
            client.fetch_courses(
                "remember_student_abc=cookie-token"
            )

        self.assertEqual(len(session.calls), 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("GET", first_url))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertTrue(session.closed)

    def test_fetch_courses_follows_redirect_between_allowed_hosts(self):
        first_url = "https://bjmf.k8n.cn/student/courses"
        second_url = "https://bj.k8n.cn/student/courses"
        session = FakeSession(
            [
                FakeResponse(
                    status_code=302,
                    headers={"Location": second_url},
                    url=first_url,
                ),
                FakeResponse(
                    text='<a href="/student/course/101">Math</a>',
                    url=second_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)

        courses = client.fetch_courses("cookie=value")

        self.assertEqual(courses, [ParsedCourse("101", "Math")])
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("GET", first_url), ("GET", second_url)],
        )
        for _, _, kwargs in session.calls:
            self.assertFalse(kwargs["allow_redirects"])
            self.assertNotIn("Cookie", kwargs["headers"])

    def test_authenticated_get_rejects_missing_or_excessive_redirects(self):
        cases = {
            "missing-location": [
                FakeResponse(status_code=302),
            ],
            "too-many": [
                FakeResponse(
                    status_code=302,
                    headers={
                        "Location": f"/student/courses?hop={index}"
                    },
                )
                for index in range(7)
            ],
        }
        for name, responses in cases.items():
            with self.subTest(name):
                session = FakeSession(responses)
                client = ClassCubeClient(
                    session_factory=lambda: session
                )

                with self.assertRaises(ClassCubeRequestError):
                    client.fetch_courses("cookie=value")

                expected_calls = 1 if name == "missing-location" else 6
                self.assertEqual(len(session.calls), expected_calls)
                self.assertTrue(session.closed)

    def test_submit_post_rejects_untrusted_redirect_before_next_request(self):
        first_url = (
            "https://bjmf.k8n.cn/student/punchs/course/1/12"
        )
        malicious_url = (
            "https://evil.k8n.cn/student/punchs/course/1/12"
        )
        session = FakeSession(
            [
                FakeResponse(
                    status_code=302,
                    headers={"Location": malicious_url},
                    url=first_url,
                ),
                FakeResponse(
                    text='<div data-status="success">Leaked</div>',
                    url=malicious_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=first_url,
            method="post",
            mode="password",
            hidden_fields={"_token": "token"},
        )

        with self.assertRaises(ClassCubeRequestError):
            client.submit_form("cookie=value", form, {})

        self.assertEqual(len(session.calls), 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("POST", first_url))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("Cookie", kwargs["headers"])

    def test_submit_post_302_follows_allowed_redirect_as_get(self):
        first_url = (
            "https://bjmf.k8n.cn/student/punchs/course/1/12"
        )
        second_url = "https://bj.k8n.cn/student/punchs/result"
        session = FakeSession(
            [
                FakeResponse(
                    status_code=302,
                    headers={"Location": second_url},
                    url=first_url,
                ),
                FakeResponse(
                    text='<div data-status="success">Done</div>',
                    url=second_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=first_url,
            method="post",
            mode="password",
            hidden_fields={"_token": "token"},
        )

        result = client.submit_form(
            "cookie=value",
            form,
            {"passcode": "1234"},
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("POST", first_url), ("GET", second_url)],
        )
        self.assertEqual(
            session.calls[0][2]["data"],
            {"_token": "token", "passcode": "1234"},
        )
        self.assertNotIn("data", session.calls[1][2])
        for _, _, kwargs in session.calls:
            self.assertFalse(kwargs["allow_redirects"])

    def test_submit_post_307_follows_allowed_redirect_as_post(self):
        first_url = (
            "https://bjmf.k8n.cn/student/punchs/course/1/12"
        )
        second_url = (
            "https://bj.k8n.cn/student/punchs/course/1/12"
        )
        session = FakeSession(
            [
                FakeResponse(
                    status_code=307,
                    headers={"Location": second_url},
                    url=first_url,
                ),
                FakeResponse(
                    text='<div data-status="success">Done</div>',
                    url=second_url,
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action=first_url,
            method="post",
            mode="password",
            hidden_fields={"_token": "token"},
        )

        result = client.submit_form(
            "cookie=value",
            form,
            {"passcode": "1234"},
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(
            [(method, url) for method, url, _ in session.calls],
            [("POST", first_url), ("POST", second_url)],
        )
        for _, _, kwargs in session.calls:
            self.assertEqual(
                kwargs["data"],
                {"_token": "token", "passcode": "1234"},
            )
            self.assertFalse(kwargs["allow_redirects"])

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
