from app.class_cube_parser import ParsedResult
from app.class_cube_client import ClassCubeSubmissionUnknown
from app.class_cube_service import ClassCubeService


def checkin_context(action: str) -> dict:
    return {
        "actor_user_id": 1,
        "is_admin": False,
        "item": {
            "id": 21,
            "course_id": 7,
            "remote_item_id": "5458535",
            "remote_module": "punch",
            "mode": "password",
            "status": "active",
            "form_action": action,
            "form_schema": {
                "method": "post",
                "mode": "password",
                "hidden_fields": {},
                "password_field": "pwd",
                "submit_capable": True,
            },
        },
        "course": {"id": 7, "account_id": 3},
        "account": {"id": 3, "status": "active", "cookie": "cookie"},
    }


class SuccessfulClient:
    def __init__(self):
        self.submitted_action = ""

    def submit_form(self, cookie, form, fields):
        self.submitted_action = form.action
        return ParsedResult(status="success")


class TimedOutClient:
    def submit_form(self, cookie, form, fields):
        raise ClassCubeSubmissionUnknown("remote POST timed out")


class UnknownResultClient:
    def submit_form(self, cookie, form, fields):
        return ParsedResult(status="unknown_result")


def test_course_center_refreshes_form_before_submitting():
    service = ClassCubeService.__new__(ClassCubeService)
    service.client = SuccessfulClient()
    stale = checkin_context("https://bjmf.k8n.cn/old")
    fresh = checkin_context(
        "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
    )
    service._refresh_manual_context = (
        lambda item_id, actor, context: fresh
    )

    result = service.manual_checkin(
        21,
        {"password": "2468"},
        {"id": 1, "role": "user"},
        context=stale,
    )

    assert result["status"] == "success"
    assert service.client.submitted_action == fresh["item"]["form_action"]


def test_closed_item_confirms_timed_out_submission_without_retry():
    service = ClassCubeService.__new__(ClassCubeService)
    service.client = TimedOutClient()
    service._log_remote_failure = lambda operation, error: None
    service._confirm_unknown_submission = (
        lambda context, actor: True
    )

    result = service.manual_checkin(
        21,
        {"password": "2468"},
        {"id": 1, "role": "user"},
        before_submit=lambda: None,
        context=checkin_context(
            "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
        ),
    )

    assert result["status"] == "success"


def test_closed_item_confirms_unrecognized_submission_response():
    service = ClassCubeService.__new__(ClassCubeService)
    service.client = UnknownResultClient()
    service._confirm_unknown_submission = (
        lambda context, actor: True
    )

    result = service.manual_checkin(
        21,
        {"password": "2468"},
        {"id": 1, "role": "user"},
        before_submit=lambda: None,
        context=checkin_context(
            "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
        ),
    )

    assert result["status"] == "success"


def test_unknown_confirmation_matches_exact_closed_remote_item():
    service = ClassCubeService.__new__(ClassCubeService)
    context = checkin_context(
        "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
    )
    service.sync_items = lambda course_id, actor: [
        {
            "remote_item_id": "other",
            "remote_module": "punch",
            "status": "closed",
        },
        {
            "remote_item_id": "5458535",
            "remote_module": "punch",
            "status": "closed",
        },
    ]

    confirm = getattr(service, "_confirm_unknown_submission", None)

    assert callable(confirm)
    assert confirm(context, {"id": 1, "role": "user"}) is True


def test_unknown_confirmation_rejects_non_closed_item_state():
    service = ClassCubeService.__new__(ClassCubeService)
    context = checkin_context(
        "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
    )
    service.sync_items = lambda course_id, actor: [
        {
            "remote_item_id": "5458535",
            "remote_module": "punch",
            "status": "unknown",
        },
    ]

    assert service._confirm_unknown_submission(
        context,
        {"id": 1, "role": "user"},
    ) is False
