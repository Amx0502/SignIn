import base64
import secrets
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable
from urllib.parse import quote, urljoin

import requests

from app.class_cube_parser import (
    ParsedCourse,
    ParsedForm,
    ParsedItem,
    ParsedResult,
    parse_checkin_form,
    parse_checkin_items,
    parse_checkin_result,
    parse_courses,
    parse_qr_image_url,
)


QR_LOGIN_URL = "https://bjmf.k8n.cn/weixin/qrlogin/student"
COURSES_URL = "https://bjmf.k8n.cn/student/courses"
CHECKIN_LIST_URL = "https://bjmf.k8n.cn/student/punchs/course/{course_id}"
QR_TTL_SECONDS = 120
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10
GET_MAX_ATTEMPTS = 3

WECHAT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/112.0.0.0 "
    "Mobile Safari/537.36 MicroMessenger/8.0"
)
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)


class QrSessionNotFound(LookupError):
    pass


class ClassCubeRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class QrSessionView:
    token: str
    qr_image_base64: str
    expires_at: float


@dataclass(frozen=True)
class QrSessionResult:
    status: str
    cookie: str = ""
    redirect_url: str = ""


@dataclass(frozen=True)
class RemoteItemBundle:
    item: ParsedItem
    form: ParsedForm


@dataclass
class _QrSession:
    owner_user_id: int
    created_at: float
    session: requests.Session


class ClassCubeClient:
    def __init__(
        self,
        session_factory: Callable[[], requests.Session] = requests.Session,
        clock: Callable[[], float] | None = None,
    ):
        self._session_factory = session_factory
        self._clock = clock or __import__("time").monotonic
        self._qr_sessions: dict[str, _QrSession] = {}
        self._qr_lock = RLock()

    def create_qr_session(self, owner_user_id: int) -> QrSessionView:
        now = self._clock()
        with self._qr_lock:
            self._cleanup_expired(now)
        session = self._session_factory()
        try:
            login_response = session.get(
                QR_LOGIN_URL,
                headers=self._request_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            login_response.raise_for_status()

            image_url = parse_qr_image_url(
                login_response.text,
                login_response.url or QR_LOGIN_URL,
            )
            if not image_url:
                raise ClassCubeRequestError(
                    "remote QR login page did not contain a QR image"
                )
            image_response = session.get(
                image_url,
                headers=self._request_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            image_response.raise_for_status()
        except requests.RequestException as exc:
            session.close()
            raise ClassCubeRequestError(
                "failed to create remote QR session"
            ) from exc
        except Exception:
            session.close()
            raise

        token = secrets.token_urlsafe(32)
        with self._qr_lock:
            self._qr_sessions[token] = _QrSession(
                owner_user_id=owner_user_id,
                created_at=now,
                session=session,
            )
        return QrSessionView(
            token=token,
            qr_image_base64=base64.b64encode(
                image_response.content
            ).decode("ascii"),
            expires_at=now + QR_TTL_SECONDS,
        )

    def fetch_courses(self, cookie: str) -> list[ParsedCourse]:
        session = self._session_factory()
        try:
            response = self._get_with_retries(
                session,
                COURSES_URL,
                cookie,
            )

            return parse_courses(response.text)
        finally:
            session.close()

    def fetch_items(
        self,
        cookie: str,
        remote_course_id: str,
    ) -> list[RemoteItemBundle]:
        session = self._session_factory()
        course_id = str(remote_course_id)
        list_url = CHECKIN_LIST_URL.format(
            course_id=quote(course_id, safe=""),
        )
        try:
            list_response = self._get_with_retries(
                session,
                list_url,
                cookie,
            )
            response_url = list_response.url or list_url
            items = parse_checkin_items(
                list_response.text,
                course_id=course_id,
                module="punchs",
                response_url=response_url,
            )
            bundles = []
            for item in items:
                if item.detail_url:
                    form_response = self._get_with_retries(
                        session,
                        item.detail_url,
                        cookie,
                    )
                    form = parse_checkin_form(
                        form_response.text,
                        form_response.url or item.detail_url,
                        item,
                    )
                else:
                    form = parse_checkin_form(
                        list_response.text,
                        response_url,
                        item,
                    )
                bundles.append(RemoteItemBundle(item=item, form=form))
            return bundles
        finally:
            session.close()

    def submit_form(
        self,
        cookie: str,
        form: ParsedForm,
        fields: dict[str, str],
        photo_path=None,
    ) -> ParsedResult:
        session = self._session_factory()
        payload = dict(form.hidden_fields)
        payload.update(fields)
        photo_file = None
        try:
            if form.method.lower() == "get":
                response = self._get_with_retries(
                    session,
                    form.action,
                    cookie,
                    params=payload,
                )
            else:
                files = None
                if photo_path is not None:
                    if not form.file_field:
                        raise ValueError(
                            "photo path requires a declared file field"
                        )
                    photo = Path(photo_path)
                    photo_file = photo.open("rb")
                    files = {
                        form.file_field: (photo.name, photo_file),
                    }
                request_kwargs = {
                    "data": payload,
                    "headers": self._request_headers(cookie),
                    "timeout": REQUEST_TIMEOUT,
                }
                if files is not None:
                    request_kwargs["files"] = files
                response = session.post(
                    form.action,
                    **request_kwargs,
                )
            response.raise_for_status()
            return parse_checkin_result(
                response.text,
                response.url or form.action,
            )
        except requests.RequestException as exc:
            raise ClassCubeRequestError(
                "check-in form submission failed"
            ) from exc
        finally:
            if photo_file is not None:
                photo_file.close()
            session.close()

    def poll_qr_session(
        self,
        token: str,
        owner_user_id: int,
    ) -> QrSessionResult:
        now = self._clock()
        with self._qr_lock:
            qr_session = self._qr_sessions.get(token)
            self._cleanup_expired(now, exclude_token=token)
            if (
                qr_session is None
                or qr_session.owner_user_id != owner_user_id
            ):
                raise QrSessionNotFound(token)
            if now - qr_session.created_at >= QR_TTL_SECONDS:
                self._remove_qr_session(token)
                return QrSessionResult(status="expired")

            try:
                response = qr_session.session.get(
                    QR_LOGIN_URL,
                    headers=self._request_headers(),
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=False,
                )
            except requests.Timeout:
                return QrSessionResult(status="timeout")
            except requests.RequestException:
                return QrSessionResult(status="error")

            if 300 <= response.status_code < 400:
                redirect_url = urljoin(
                    QR_LOGIN_URL,
                    response.headers.get("Location", ""),
                )
                cookie = self._remember_student_cookie(
                    qr_session.session,
                    response,
                )
                self._remove_qr_session(token)
                return QrSessionResult(
                    status="success",
                    cookie=cookie,
                    redirect_url=redirect_url,
                )

            try:
                response.raise_for_status()
            except requests.RequestException:
                return QrSessionResult(status="error")

            status = self._poll_status(response)
            if status in {"success", "expired", "error"}:
                cookie = self._remember_student_cookie(
                    qr_session.session,
                    response,
                )
                self._remove_qr_session(token)
                return QrSessionResult(status=status, cookie=cookie)
            return QrSessionResult(status=status)

    def _get_with_retries(
        self,
        session,
        url: str,
        cookie: str,
        **request_kwargs,
    ):
        last_error = None
        for _ in range(GET_MAX_ATTEMPTS):
            try:
                response = session.get(
                    url,
                    headers=self._request_headers(cookie),
                    timeout=REQUEST_TIMEOUT,
                    **request_kwargs,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
        raise ClassCubeRequestError(
            f"GET request failed after {GET_MAX_ATTEMPTS} attempts"
        ) from last_error

    @staticmethod
    def _request_headers(cookie: str = "") -> dict[str, str]:
        headers = {"User-Agent": WECHAT_USER_AGENT}
        if cookie:
            headers["Cookie"] = cookie
        return headers

    @staticmethod
    def _poll_status(response) -> str:
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return "pending"
        if not isinstance(payload, dict):
            return "pending"
        value = payload.get(
            "status",
            payload.get("state", payload.get("code", "pending")),
        )
        normalized = str(value).strip().lower()
        if value is False or normalized in {
            "",
            "0",
            "pending",
            "wait",
            "waiting",
        }:
            return "pending"
        if value is True or normalized in {
            "1",
            "ok",
            "success",
            "complete",
            "completed",
        }:
            return "success"
        if normalized in {"expired", "timeout"}:
            return "expired"
        if normalized in {"error", "failed", "failure"}:
            return "error"
        return "pending"

    @staticmethod
    def _remember_student_cookie(session, response) -> str:
        cookies: dict[str, str] = {}
        for jar in (
            getattr(session, "cookies", ()),
            getattr(response, "cookies", ()),
        ):
            for cookie in jar:
                if cookie.name.startswith("remember_student_"):
                    cookies[cookie.name] = cookie.value
        return "; ".join(
            f"{name}={value}" for name, value in sorted(cookies.items())
        )

    def _cleanup_expired(
        self,
        now: float,
        exclude_token: str | None = None,
    ) -> None:
        expired_tokens = [
            token
            for token, qr_session in self._qr_sessions.items()
            if token != exclude_token
            and now - qr_session.created_at >= QR_TTL_SECONDS
        ]
        for token in expired_tokens:
            self._remove_qr_session(token)

    def _remove_qr_session(self, token: str) -> None:
        qr_session = self._qr_sessions.pop(token, None)
        if qr_session is not None:
            qr_session.session.close()
