import json

import pytest

from app.class_cube_client import ClassCubeClient
from app.class_cube_parser import ParsedForm, parse_checkin_result
from app.class_cube_service import (
    CheckinParameters,
    ClassCubeValidationError,
    build_submission_fields,
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.url = "https://bjmf.k8n.cn/student/oss-upload-key"
        self.text = json.dumps(payload or {})

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, credential_response=None, upload_response=None):
        self.credential_response = credential_response
        self.upload_response = upload_response
        self.get_calls = []
        self.post_calls = []
        self.cookies = {}
        self.closed = False

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.credential_response

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.upload_response

    def close(self):
        self.closed = True


def _gps_photo_form():
    return ParsedForm(
        action="https://bjmf.k8n.cn/student/punchw/course/1/2",
        method="post",
        mode="gps_photo",
        hidden_fields={},
        item_id_field="",
        latitude_field="lat",
        longitude_field="lng",
        accuracy_field="acc",
        photo_resource_field="res",
        submit_capable=True,
    )


def test_gps_photo_requires_an_uploaded_resource_and_serializes_res_array():
    fields = build_submission_fields(
        _gps_photo_form(),
        CheckinParameters(latitude=26.03, longitude=119.21, accuracy=20),
        remote_photo_value="p/260801/photo.png",
    )

    assert fields["res"] == '["p/260801/photo.png"]'

    with pytest.raises(ClassCubeValidationError, match="上传照片"):
        build_submission_fields(
            _gps_photo_form(),
            CheckinParameters(latitude=26.03, longitude=119.21, accuracy=20),
        )


def test_upload_photo_to_oss_uses_signed_fields_and_returns_object_key(tmp_path):
    photo = tmp_path / "huitou.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    credential_response = FakeResponse(
        {
            "accessid": "temporary-access-id",
            "host": "https://kkb.oss-cn-qingdao.aliyuncs.com",
            "policy": "signed-policy",
            "signature": "signed-signature",
            "expire": 1785565634,
            "callback": "signed-callback",
            "dir": "b/p/260801",
        }
    )
    upload_response = FakeResponse({}, status_code=204)
    credential_session = FakeSession(credential_response=credential_response)
    upload_session = FakeSession(upload_response=upload_response)

    client = ClassCubeClient(
        session_factory=lambda: credential_session,
        upload_session_factory=lambda: upload_session,
    )
    resource = client.upload_photo_to_oss("session-cookie", photo)

    assert resource.startswith("b/p/260801/")
    assert resource.endswith(".png")
    assert credential_session.get_calls[0][0].endswith(
        "/student/oss-upload-key?type=punch_from_wxapp"
    )
    upload_url, kwargs = upload_session.post_calls[0]
    assert upload_url == "https://kkb.oss-cn-qingdao.aliyuncs.com"
    assert kwargs["data"]["policy"] == "signed-policy"
    assert kwargs["data"]["OSSAccessKeyId"] == "temporary-access-id"
    assert kwargs["data"]["signature"] == "signed-signature"
    assert kwargs["data"]["callback"] == "signed-callback"
    assert kwargs["data"]["key"] == resource
    assert kwargs["files"]["file"][0] == "huitou.png"


def test_json_checkin_success_response_is_parsed_as_success():
    result = parse_checkin_result(
        '{"success":true,"message":"签到成功",'
        '"data":{"punchstatus":"ok"}}',
        "https://k8n.cn/student/punchw/course/140242/5459289",
    )

    assert result.status == "success"
    assert result.message == "签到成功"
