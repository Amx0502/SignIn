import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from pydantic import ValidationError

from app import config
from app.class_cube_client import (
    ClassCubeClient,
    ClassCubeCookieExpired,
    ClassCubeRequestError,
    ClassCubeSubmissionUnknown,
)
from app.class_cube_models import ManualCheckinRequest
from app.class_cube_parser import (
    ParsedForm,
    ParsedItem,
    ParsedResult,
    parse_checkin_form,
)
from app.class_cube_service import (
    CheckinParameters,
    ClassCubeService,
    ClassCubeValidationError,
    build_submission_fields,
)
from app.class_cube_repository import ClassCubeNotFound
from app.class_cube_router import create_class_cube_router
from test_class_cube_client import FakeResponse, FakeSession


class ClassCubeCheckinFormContractTest(unittest.TestCase):
    def setUp(self):
        self.item = ParsedItem(
            remote_item_id="item-12",
            course_id="course-1",
            remote_module="punchs",
            detail_url=(
                "https://bjmf.k8n.cn/student/punchs/"
                "course/course-1/item-12"
            ),
        )

    def test_parses_canonical_dynamic_field_mapping(self):
        form = parse_checkin_form(
            """
            <form action="/student/punchs/course/course-1/item-12"
                  method="post">
              <input type="hidden" name="id" value="">
              <input type="hidden" name="csrf" value="keep-me">
              <input name="latitude">
              <input name="longitude">
              <input name="accuracy">
              <input name="gps_addr">
              <input type="text" name="passcode">
              <input type="file" name="proof">
              <input type="hidden" name="res" value="">
            </form>
            """,
            self.item.detail_url,
            self.item,
        )

        self.assertTrue(form.submit_capable)
        self.assertEqual(form.item_id_field, "id")
        self.assertEqual(form.latitude_field, "latitude")
        self.assertEqual(form.longitude_field, "longitude")
        self.assertEqual(form.accuracy_field, "accuracy")
        self.assertEqual(form.gps_address_field, "gps_addr")
        self.assertEqual(form.password_field, "passcode")
        self.assertEqual(form.file_field, "proof")
        self.assertEqual(form.photo_resource_field, "res")

    def test_password_alias_is_detected_even_when_input_is_text(self):
        form = parse_checkin_form(
            """
            <form action="/student/daka/course/course-1/item-12"
                  method="post">
              <input type="text" name="pwd">
            </form>
            """,
            self.item.detail_url,
            self.item,
        )

        self.assertEqual(form.mode, "password")
        self.assertEqual(form.password_field, "pwd")

    def test_missing_form_is_not_treated_as_submit_capable(self):
        form = parse_checkin_form(
            "<main>普通详情页，没有签到表单</main>",
            self.item.detail_url,
            self.item,
        )

        self.assertFalse(form.submit_capable)

    def test_strict_punch_gps_marker_synthesizes_post_contract(self):
        item = ParsedItem(
            remote_item_id="22",
            course_id="1",
            remote_module="punch_gps",
            mode_hint="gps",
        )

        form = parse_checkin_form(
            '<button onclick="punch_gps(22)">GPS 签到</button>',
            "https://bjmf.k8n.cn/student/punchs/course/1",
            item,
        )

        self.assertTrue(form.submit_capable)
        self.assertEqual(form.method, "post")
        self.assertEqual(
            form.action,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/22",
        )
        self.assertEqual(form.item_id_field, "id")
        self.assertEqual(form.latitude_field, "lat")
        self.assertEqual(form.longitude_field, "lng")
        self.assertEqual(form.accuracy_field, "acc")
        self.assertEqual(form.gps_address_field, "gps_addr")

    def test_strict_punchcard_marker_synthesizes_qr_post_contract(self):
        item = ParsedItem(
            remote_item_id="23",
            course_id="1",
            remote_module="punchs",
            mode_hint="qr",
        )

        form = parse_checkin_form(
            '<section id="punchcard_23">二维码签到</section>',
            "https://bjmf.k8n.cn/student/punchs/course/1",
            item,
        )

        self.assertTrue(form.submit_capable)
        self.assertEqual(form.mode, "qr")
        self.assertEqual(form.method, "post")
        self.assertEqual(
            form.action,
            "https://bjmf.k8n.cn/student/punchs/course/1/23",
        )
        self.assertEqual(form.item_id_field, "id")

    def test_exact_known_route_can_synthesize_recognized_qr_contract(self):
        item = ParsedItem(
            remote_item_id="24",
            course_id="1",
            remote_module="daka",
            detail_url=(
                "https://bjmf.k8n.cn/student/daka/course/1/24"
            ),
            mode_hint="qr",
        )

        form = parse_checkin_form(
            "<main>签到详情由脚本提交</main>",
            item.detail_url,
            item,
        )

        self.assertTrue(form.submit_capable)
        self.assertEqual(form.action, item.detail_url)
        self.assertEqual(form.method, "post")
        self.assertEqual(form.item_id_field, "id")

    def test_explicit_separate_upload_contract_is_parsed(self):
        form = parse_checkin_form(
            """
            <form action="/student/punch_gps/course/course-1/item-12"
                  method="post"
                  data-upload-action="/student/uploads/checkin-photo"
                  data-upload-file-field="image"
                  data-upload-response-key="data.resource">
              <input name="lat">
              <input name="lng">
              <input type="hidden" name="res" value="">
            </form>
            """,
            self.item.detail_url,
            self.item,
        )

        self.assertEqual(form.mode, "gps_photo")
        self.assertEqual(
            form.upload_action,
            "https://bjmf.k8n.cn/student/uploads/checkin-photo",
        )
        self.assertEqual(form.upload_method, "post")
        self.assertEqual(form.upload_file_field, "image")
        self.assertEqual(form.upload_response_key, "data.resource")
        self.assertEqual(form.photo_resource_field, "res")

    def test_gps_with_resource_field_stays_photo_mode_without_upload_contract(self):
        form = parse_checkin_form(
            """
            <form action="/student/punch_gps/course/course-1/item-12"
                  method="post">
              <input name="lat">
              <input name="lng">
              <input type="hidden" name="res" value="">
            </form>
            """,
            self.item.detail_url,
            self.item,
        )

        self.assertEqual(form.mode, "gps_photo")
        self.assertEqual(form.photo_resource_field, "res")
        self.assertEqual(form.file_field, "")
        self.assertEqual(form.upload_action, "")


class ClassCubeSubmissionFieldTest(unittest.TestCase):
    def test_builds_qr_fields_without_accepting_arbitrary_payload(self):
        form = parse_checkin_form(
            """
            <section id="punchcard_9">
              <form action="/student/punchs/course/1/9" method="post">
                <input type="hidden" name="_token" value="keep">
                <input type="hidden" name="id" value="">
              </form>
            </section>
            """,
            "https://bjmf.k8n.cn/student/punchs/course/1/9",
            ParsedItem("9", "1", remote_module="punchs"),
        )

        fields = build_submission_fields(
            form,
            CheckinParameters(),
            remote_item_id="9",
        )

        self.assertEqual(fields, {"id": "9"})
        self.assertNotIn("_token", fields)

    def test_builds_gps_photo_fields_from_actual_names(self):
        form = parse_checkin_form(
            """
            <form action="/student/punch_gps/course/1/9" method="post">
              <input name="latitude">
              <input name="longitude">
              <input name="accuracy">
              <input name="address">
              <input type="hidden" name="resource_id" value="">
            </form>
            """,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            ParsedItem("9", "1", remote_module="punch_gps"),
        )

        fields = build_submission_fields(
            form,
            CheckinParameters(
                latitude=30.1,
                longitude=120.2,
                accuracy=30,
            ),
            remote_item_id="9",
            remote_photo_value="resource-1",
        )

        self.assertEqual(
            fields,
            {
                "latitude": "30.1",
                "longitude": "120.2",
                "accuracy": "30",
                "address": "",
                "resource_id": "resource-1",
            },
        )

    def test_zero_coordinates_are_valid(self):
        form = parse_checkin_form(
            """
            <form method="post">
              <input name="lat"><input name="lng">
            </form>
            """,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            ParsedItem("9", "1", remote_module="punch_gps"),
        )

        fields = build_submission_fields(
            form,
            CheckinParameters(latitude=0, longitude=0),
            remote_item_id="9",
        )

        self.assertEqual(fields, {"lat": "0", "lng": "0"})

    def test_declared_accuracy_requires_value(self):
        form = parse_checkin_form(
            """
            <form method="post">
              <input name="lat"><input name="lng"><input name="acc">
            </form>
            """,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            ParsedItem("9", "1", remote_module="punch_gps"),
        )

        with self.assertRaisesRegex(
            ClassCubeValidationError,
            "精度",
        ):
            build_submission_fields(
                form,
                CheckinParameters(latitude=30, longitude=120),
                remote_item_id="9",
            )

    def test_rejects_non_finite_or_out_of_range_coordinates(self):
        form = parse_checkin_form(
            """
            <form method="post">
              <input name="lat"><input name="lng">
            </form>
            """,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            ParsedItem("9", "1", remote_module="punch_gps"),
        )
        cases = [
            (float("nan"), 120),
            (float("inf"), 120),
            (91, 120),
            (30, -181),
        ]

        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                with self.assertRaises(ClassCubeValidationError):
                    build_submission_fields(
                        form,
                        CheckinParameters(
                            latitude=latitude,
                            longitude=longitude,
                        ),
                        remote_item_id="9",
                    )

    def test_password_uses_detected_actual_name(self):
        form = parse_checkin_form(
            '<form method="post"><input name="code"></form>',
            "https://bjmf.k8n.cn/student/daka/course/1/9",
            ParsedItem("9", "1", remote_module="daka"),
        )

        fields = build_submission_fields(
            form,
            CheckinParameters(password=" 1234 "),
            remote_item_id="9",
        )

        self.assertEqual(fields, {"code": " 1234 "})

    def test_manual_request_enforces_secret_and_path_lengths(self):
        with self.assertRaises(ValidationError):
            ManualCheckinRequest(password="x" * 129)
        with self.assertRaises(ValidationError):
            ManualCheckinRequest(photo_path="x" * 513)


class ClassCubeRemoteSubmissionTest(unittest.TestCase):
    def test_post_timeout_has_unknown_semantics_and_is_not_retried(self):
        session = FakeSession(
            [
                requests.Timeout("secret remote timeout"),
                FakeResponse(
                    text='<div data-status="success">不应请求</div>'
                ),
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action="https://bjmf.k8n.cn/student/punchs/course/1/9",
            method="post",
            mode="qr",
            hidden_fields={},
            item_id_field="id",
            submit_capable=True,
        )

        with self.assertRaises(ClassCubeSubmissionUnknown):
            client.submit_form("cookie=value", form, {"id": "9"})

        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.closed)

    def test_explicit_upload_contract_returns_strict_nested_resource(self):
        session = FakeSession(
            [
                FakeResponse(
                    json_data={
                        "data": {"resource": "remote-resource-9"}
                    }
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action="https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            method="post",
            mode="gps_photo",
            hidden_fields={},
            photo_resource_field="res",
            submit_capable=True,
            upload_action=(
                "https://bjmf.k8n.cn/student/uploads/checkin-photo"
            ),
            upload_method="post",
            upload_file_field="image",
            upload_response_key="data.resource",
        )
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "proof.jpg"
            photo.write_bytes(b"\xff\xd8\xffphoto")

            resource = client.upload_photo(
                "cookie=value",
                form,
                photo,
            )

        self.assertEqual(resource, "remote-resource-9")
        self.assertEqual(session.uploaded_files["image"], b"\xff\xd8\xffphoto")
        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.closed)

    def test_untrusted_upload_action_is_rejected_before_request(self):
        session = FakeSession(
            [FakeResponse(json_data={"resource": "leaked"})]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action="https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            method="post",
            mode="gps_photo",
            hidden_fields={},
            submit_capable=True,
            photo_resource_field="res",
            upload_action="https://evil.example/upload",
            upload_method="post",
            upload_file_field="image",
            upload_response_key="resource",
        )

        with self.assertRaises(ClassCubeRequestError):
            client.upload_photo("cookie=value", form, "proof.jpg")

        self.assertEqual(session.calls, [])

    def test_direct_multipart_never_submits_empty_resource_field(self):
        session = FakeSession(
            [
                FakeResponse(
                    text='<div data-status="success">完成</div>'
                )
            ]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action="https://bjmf.k8n.cn/student/punch_gps/course/1/9",
            method="post",
            mode="gps_photo",
            hidden_fields={"_token": "keep", "res": ""},
            file_field="proof",
            photo_resource_field="res",
            submit_capable=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "proof.jpg"
            photo.write_bytes(b"\xff\xd8\xffphoto")

            client.submit_form(
                "cookie=value",
                form,
                {"lat": "30", "lng": "120"},
                photo_path=photo,
            )

        self.assertEqual(
            session.calls[0][2]["data"],
            {
                "_token": "keep",
                "lat": "30",
                "lng": "120",
            },
        )

    def test_non_submit_capable_form_is_rejected_before_request(self):
        session = FakeSession(
            [FakeResponse(text='<div data-status="success">bad</div>')]
        )
        client = ClassCubeClient(session_factory=lambda: session)
        form = ParsedForm(
            action="https://bjmf.k8n.cn/student/punchs/course/1/9",
            method="get",
            mode="qr",
            hidden_fields={},
            submit_capable=False,
        )

        with self.assertRaises(ClassCubeRequestError):
            client.submit_form("cookie=value", form, {})

        self.assertEqual(session.calls, [])


class ManualCheckinRepository:
    def __init__(self):
        self.accounts = {
            1: {
                "id": 1,
                "owner_user_id": 7,
                "cookie": "remember_student_owner=top-secret",
                "status": "active",
            }
        }
        self.courses = {
            11: {
                "id": 11,
                "account_id": 1,
                "remote_course_id": "course-1",
            }
        }
        self.items = {}
        self.expired = []

    @staticmethod
    def _allowed(account, actor_user_id, is_admin):
        return is_admin or account["owner_user_id"] == actor_user_id

    def get_account(self, account_id, actor_user_id, is_admin):
        account = self.accounts.get(account_id)
        if account is None or not self._allowed(
            account,
            actor_user_id,
            is_admin,
        ):
            raise ClassCubeNotFound("账号不存在")
        return dict(account)

    def get_course(self, course_id, actor_user_id, is_admin):
        course = self.courses.get(course_id)
        if course is None:
            raise ClassCubeNotFound("课程不存在")
        self.get_account(
            course["account_id"],
            actor_user_id,
            is_admin,
        )
        return dict(course)

    def get_item(self, item_id, actor_user_id, is_admin):
        item = self.items.get(item_id)
        if item is None:
            raise ClassCubeNotFound("签到项不存在")
        self.get_course(
            item["course_id"],
            actor_user_id,
            is_admin,
        )
        return dict(item)

    def mark_account_expired(
        self,
        account_id,
        actor_user_id,
        is_admin,
    ):
        account = self.get_account(
            account_id,
            actor_user_id,
            is_admin,
        )
        self.accounts[account_id]["status"] = "expired"
        self.expired.append(account_id)
        account["status"] = "expired"
        return account


class ManualCheckinClient:
    def __init__(self):
        self.calls = []
        self.result = ParsedResult(
            "success",
            "签到成功",
            "https://bjmf.k8n.cn/result",
        )
        self.upload_resource = "remote-photo-1"

    def submit_form(
        self,
        cookie,
        form,
        fields,
        photo_path=None,
    ):
        self.calls.append(
            (
                "submit",
                cookie,
                form,
                dict(fields),
                photo_path,
            )
        )
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def upload_photo(self, cookie, form, photo_path):
        self.calls.append(
            ("upload", cookie, form, photo_path)
        )
        if isinstance(self.upload_resource, BaseException):
            raise self.upload_resource
        return self.upload_resource

    def close(self):
        pass


class SilentLogger:
    def __init__(self):
        self.records = []

    def warning(self, template, *args):
        self.records.append(template % args)

    def error(self, template, *args):
        self.records.append(template % args)


def stored_form(form: ParsedForm) -> dict:
    return {
        "method": form.method,
        "mode": form.mode,
        "hidden_fields": dict(form.hidden_fields),
        "password_field": form.password_field,
        "file_field": form.file_field,
        "item_id_field": form.item_id_field,
        "latitude_field": form.latitude_field,
        "longitude_field": form.longitude_field,
        "accuracy_field": form.accuracy_field,
        "gps_address_field": form.gps_address_field,
        "photo_resource_field": form.photo_resource_field,
        "submit_capable": form.submit_capable,
        "upload_action": form.upload_action,
        "upload_method": form.upload_method,
        "upload_file_field": form.upload_file_field,
        "upload_response_key": form.upload_response_key,
    }


class ClassCubeManualCheckinServiceTest(unittest.TestCase):
    def setUp(self):
        self.repository = ManualCheckinRepository()
        self.client = ManualCheckinClient()
        self.logger = SilentLogger()
        self.service = ClassCubeService(
            self.repository,
            self.client,
            self.logger,
        )
        self.actor = {"id": 7, "role": "user"}

    def add_item(self, item_id, mode, form):
        self.repository.items[item_id] = {
            "id": item_id,
            "course_id": 11,
            "remote_item_id": f"remote-{item_id}",
            "mode": mode,
            "remote_module": "punchs",
            "form_action": form.action,
            "form_schema": stored_form(form),
            "status": "active",
        }

    @staticmethod
    def form(mode, **kwargs):
        defaults = {
            "action": (
                "https://bjmf.k8n.cn/student/punchs/"
                "course/course-1/item-1"
            ),
            "method": "post",
            "mode": mode,
            "hidden_fields": {"_token": "hidden-secret"},
            "submit_capable": True,
        }
        defaults.update(kwargs)
        return ParsedForm(**defaults)

    def test_qr_submits_only_detected_item_field_and_returns_safe_view(self):
        self.add_item(
            21,
            "qr",
            self.form("qr", item_id_field="id"),
        )

        result = self.service.manual_checkin(
            21,
            {"unexpected": "must-not-forward"},
            self.actor,
        )

        self.assertEqual(result, {
            "status": "success",
            "message": "签到成功",
        })
        self.assertEqual(
            self.client.calls[0][3],
            {"id": "remote-21"},
        )
        self.assertNotIn("cookie", result)
        self.assertNotIn("form_schema", result)

    def test_password_without_value_waits_without_posting(self):
        self.add_item(
            22,
            "password",
            self.form("password", password_field="passcode"),
        )

        result = self.service.manual_checkin(22, {}, self.actor)

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(self.client.calls, [])

    def test_password_temporary_override_is_not_persisted(self):
        self.add_item(
            23,
            "password",
            self.form("password", password_field="code"),
        )
        before = repr(self.repository.items)

        result = self.service.manual_checkin(
            23,
            {"password": "one-time-password"},
            self.actor,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            self.client.calls[0][3],
            {"code": "one-time-password"},
        )
        self.assertEqual(repr(self.repository.items), before)

    def test_gps_requires_complete_valid_coordinates_before_post(self):
        self.add_item(
            24,
            "gps",
            self.form(
                "gps",
                latitude_field="lat",
                longitude_field="lng",
                accuracy_field="acc",
            ),
        )

        result = self.service.manual_checkin(
            24,
            {"latitude": 30, "longitude": 120},
            self.actor,
        )

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(self.client.calls, [])

    def test_photo_resource_without_upload_contract_waits_without_request(self):
        self.add_item(
            241,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                photo_resource_field="res",
            ),
        )

        result = self.service.manual_checkin(
            241,
            {
                "latitude": 30,
                "longitude": 120,
                "photo_path": "class-cube/7/proof.jpg",
            },
            self.actor,
        )

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(self.client.calls, [])

    def test_non_submit_capable_form_waits_without_request(self):
        self.add_item(
            25,
            "qr",
            self.form(
                "qr",
                submit_capable=False,
                method="get",
            ),
        )

        result = self.service.manual_checkin(25, {}, self.actor)

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(self.client.calls, [])

    def test_plain_200_unknown_result_is_not_promoted_to_success(self):
        self.add_item(
            26,
            "qr",
            self.form("qr", item_id_field="id"),
        )
        self.client.result = ParsedResult(
            "unknown_result",
            "处理中 remember_student_owner=top-secret",
        )

        result = self.service.manual_checkin(26, {}, self.actor)

        self.assertEqual(result["status"], "unknown_result")
        self.assertNotIn("top-secret", repr(result))

    def test_post_timeout_returns_unknown_result_without_secret(self):
        self.add_item(
            27,
            "qr",
            self.form("qr", item_id_field="id"),
        )
        self.client.result = ClassCubeSubmissionUnknown(
            "timeout included top-secret"
        )

        result = self.service.manual_checkin(27, {}, self.actor)

        self.assertEqual(result["status"], "unknown_result")
        self.assertNotIn("top-secret", repr(result))

    def test_cookie_expired_marks_account_and_returns_sanitized_failure(self):
        self.add_item(
            28,
            "qr",
            self.form("qr", item_id_field="id"),
        )
        self.client.result = ParsedResult(
            "cookie_expired",
            "remember_student_owner=top-secret",
        )

        result = self.service.manual_checkin(28, {}, self.actor)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.repository.expired, [1])
        self.assertEqual(
            self.repository.accounts[1]["status"],
            "expired",
        )
        self.assertNotIn("top-secret", repr(result))

    def test_remote_failure_returns_fixed_sanitized_failure(self):
        self.add_item(
            29,
            "qr",
            self.form("qr", item_id_field="id"),
        )
        self.client.result = ClassCubeRequestError(
            "failed with remember_student_owner=top-secret"
        )

        result = self.service.manual_checkin(29, {}, self.actor)

        self.assertEqual(result["status"], "failed")
        self.assertNotIn(
            "top-secret",
            repr((result, self.logger.records)),
        )

    def test_direct_multipart_uses_only_valid_owned_photo_path(self):
        self.add_item(
            30,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                file_field="proof",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            owner_dir = upload_root / "class-cube" / "7"
            owner_dir.mkdir(parents=True)
            photo = owner_dir / "proof.jpg"
            photo.write_bytes(b"\xff\xd8\xffvalid-photo")
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.manual_checkin(
                    30,
                    {
                        "latitude": 30,
                        "longitude": 120,
                        "photo_path": (
                            "class-cube/7/proof.jpg"
                        ),
                    },
                    self.actor,
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            self.client.calls[0][4],
            photo.resolve(),
        )

    def test_manual_photo_rejects_traversal_cross_owner_and_bad_signature(self):
        self.add_item(
            31,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                file_field="proof",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            own = upload_root / "class-cube" / "7"
            other = upload_root / "class-cube" / "8"
            own.mkdir(parents=True)
            other.mkdir(parents=True)
            (own / "bad.jpg").write_bytes(b"not-an-image")
            (other / "proof.jpg").write_bytes(
                b"\xff\xd8\xffother-photo"
            )
            cases = [
                "../proof.jpg",
                r"class-cube\7\..\8\proof.jpg",
                "class-cube/8/proof.jpg",
                str((other / "proof.jpg").resolve()),
                "class-cube/7/bad.jpg",
            ]
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                for photo_path in cases:
                    with self.subTest(photo_path=photo_path):
                        result = self.service.manual_checkin(
                            31,
                            {
                                "latitude": 30,
                                "longitude": 120,
                                "photo_path": photo_path,
                            },
                            self.actor,
                        )
                        self.assertEqual(
                            result["status"],
                            "waiting_parameter",
                        )
            self.assertEqual(self.client.calls, [])

    def test_manual_photo_rejects_symlink_escape(self):
        self.add_item(
            32,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                file_field="proof",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            owner_dir = upload_root / "class-cube" / "7"
            owner_dir.mkdir(parents=True)
            outside = Path(directory) / "outside.jpg"
            outside.write_bytes(b"\xff\xd8\xffoutside")
            link = owner_dir / "link.jpg"
            try:
                os.symlink(outside, link)
            except OSError as exc:
                self.skipTest(f"当前环境不能创建符号链接: {exc}")
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.manual_checkin(
                    32,
                    {
                        "latitude": 30,
                        "longitude": 120,
                        "photo_path": "class-cube/7/link.jpg",
                    },
                    self.actor,
                )

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(self.client.calls, [])

    def test_separate_upload_uses_valid_photo_then_resource_field(self):
        self.add_item(
            33,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                photo_resource_field="res",
                upload_action=(
                    "https://bjmf.k8n.cn/student/uploads/photo"
                ),
                upload_method="post",
                upload_file_field="image",
                upload_response_key="data.resource",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            owner_dir = upload_root / "class-cube" / "7"
            owner_dir.mkdir(parents=True)
            (owner_dir / "proof.png").write_bytes(
                b"\x89PNG\r\n\x1a\nvalid"
            )
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.manual_checkin(
                    33,
                    {
                        "latitude": 30,
                        "longitude": 120,
                        "photo_path": (
                            "class-cube/7/proof.png"
                        ),
                    },
                    self.actor,
                )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            [call[0] for call in self.client.calls],
            ["upload", "submit"],
        )
        self.assertEqual(
            self.client.calls[1][3]["res"],
            "remote-photo-1",
        )
        self.assertIsNone(self.client.calls[1][4])

    def test_upload_timeout_is_waiting_not_final_submission_unknown(self):
        self.add_item(
            34,
            "gps_photo",
            self.form(
                "gps_photo",
                latitude_field="lat",
                longitude_field="lng",
                photo_resource_field="res",
                upload_action=(
                    "https://bjmf.k8n.cn/student/uploads/photo"
                ),
                upload_method="post",
                upload_file_field="image",
                upload_response_key="data.resource",
            ),
        )
        self.client.upload_resource = ClassCubeSubmissionUnknown(
            "upload timed out"
        )
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            owner_dir = upload_root / "class-cube" / "7"
            owner_dir.mkdir(parents=True)
            (owner_dir / "proof.webp").write_bytes(
                b"RIFF\x04\x00\x00\x00WEBPvalid"
            )
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.manual_checkin(
                    34,
                    {
                        "latitude": 30,
                        "longitude": 120,
                        "photo_path": (
                            "class-cube/7/proof.webp"
                        ),
                    },
                    self.actor,
                )

        self.assertEqual(result["status"], "waiting_parameter")
        self.assertEqual(
            [call[0] for call in self.client.calls],
            ["upload"],
        )


def make_upload(
    name: str,
    content_type: str,
    content: bytes,
) -> UploadFile:
    return UploadFile(
        filename=name,
        file=io.BytesIO(content),
        headers={"content-type": content_type},
    )


class ClassCubeLocalPhotoTest(unittest.TestCase):
    def setUp(self):
        self.repository = ManualCheckinRepository()
        self.service = ClassCubeService(
            self.repository,
            ManualCheckinClient(),
            SilentLogger(),
        )
        self.actor = {"id": 7, "role": "user"}

    def test_saves_valid_photo_under_actual_owner_with_safe_relative_view(self):
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.save_photo(
                    make_upload(
                        "proof.jpeg",
                        "image/jpeg",
                        b"\xff\xd8\xffvalid-jpeg",
                    ),
                    self.actor,
                )
                saved = upload_root / result["path"]

                self.assertTrue(saved.is_file())
                self.assertTrue(
                    result["path"].startswith("class-cube/7/")
                )
                self.assertEqual(
                    result["url"],
                    f"/uploads/{result['path']}",
                )
                self.assertNotIn(str(upload_root), repr(result))

    def test_admin_account_context_resolves_cross_user_owner(self):
        self.repository.accounts[2] = {
            "id": 2,
            "owner_user_id": 8,
            "cookie": "secret",
            "status": "active",
        }
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                result = self.service.save_photo(
                    make_upload(
                        "proof.png",
                        "image/png",
                        b"\x89PNG\r\n\x1a\nvalid",
                    ),
                    {"id": 99, "role": "admin"},
                    account_id=2,
                )

        self.assertTrue(
            result["path"].startswith("class-cube/8/")
        )

    def test_rejects_extension_mime_and_signature_mismatch(self):
        cases = [
            ("proof.exe", "image/jpeg", b"\xff\xd8\xffx"),
            ("proof.jpg", "image/png", b"\xff\xd8\xffx"),
            ("proof.webp", "image/webp", b"not-webp"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                for name, content_type, content in cases:
                    with self.subTest(name=name):
                        with self.assertRaises(
                            ClassCubeValidationError
                        ):
                            self.service.save_photo(
                                make_upload(
                                    name,
                                    content_type,
                                    content,
                                ),
                                self.actor,
                            )
                self.assertEqual(
                    list(upload_root.rglob("*"))
                    if upload_root.exists()
                    else [],
                    [],
                )

    def test_rejects_file_over_ten_megabytes_and_cleans_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                with self.assertRaisesRegex(
                    ClassCubeValidationError,
                    "10MB",
                ):
                    self.service.save_photo(
                        make_upload(
                            "proof.jpg",
                            "image/jpeg",
                            b"\xff\xd8\xff"
                            + b"x" * (10 * 1024 * 1024),
                        ),
                        self.actor,
                    )
                files = [
                    path
                    for path in upload_root.rglob("*")
                    if path.is_file()
                ]
                self.assertEqual(files, [])


class ClassCubeCheckinRouterTest(unittest.TestCase):
    def setUp(self):
        self.repository = ManualCheckinRepository()
        self.remote_client = ManualCheckinClient()
        self.service = ClassCubeService(
            self.repository,
            self.remote_client,
            SilentLogger(),
        )
        form = ParsedForm(
            action=(
                "https://bjmf.k8n.cn/student/punchs/"
                "course/course-1/remote-21"
            ),
            method="post",
            mode="qr",
            hidden_fields={"_token": "secret"},
            item_id_field="id",
            submit_capable=True,
        )
        self.repository.items[21] = {
            "id": 21,
            "course_id": 11,
            "remote_item_id": "remote-21",
            "mode": "qr",
            "remote_module": "punchs",
            "form_action": form.action,
            "form_schema": stored_form(form),
            "status": "active",
        }
        self.auth_calls = 0

        def current_user():
            self.auth_calls += 1
            return {"id": 7, "role": "user"}

        app = FastAPI()
        app.state.class_cube_service = self.service
        app.include_router(
            create_class_cube_router(current_user)
        )
        self.client = TestClient(app)

    def test_manual_checkin_route_uses_auth_and_success_envelope(self):
        response = self.client.post(
            "/api/class-cube/items/21/checkin",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "data": {
                    "status": "success",
                    "message": "签到成功",
                },
            },
        )
        self.assertEqual(self.auth_calls, 1)

    def test_photo_route_uses_auth_and_returns_only_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            upload_root = Path(directory) / "uploads"
            with (
                patch.object(config, "UPLOAD_DIR", upload_root),
                patch.object(
                    config,
                    "CLASS_CUBE_UPLOAD_DIR",
                    upload_root / "class-cube",
                ),
            ):
                response = self.client.post(
                    "/api/class-cube/photos",
                    files={
                        "file": (
                            "proof.png",
                            b"\x89PNG\r\n\x1a\nvalid",
                            "image/png",
                        )
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            set(payload["data"]),
            {"path", "url"},
        )
        self.assertTrue(
            payload["data"]["path"].startswith(
                "class-cube/7/"
            )
        )
        self.assertNotIn(str(upload_root), repr(payload))
        self.assertEqual(self.auth_calls, 1)

if __name__ == "__main__":
    unittest.main()
