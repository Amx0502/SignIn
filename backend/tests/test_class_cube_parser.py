from app.class_cube_parser import (
    parse_checkin_form,
    parse_checkin_items,
)
from app.class_cube_service import (
    CheckinParameters,
    build_submission_fields,
)


INLINE_PASSWORD_HTML = """
<div class="card punch-card punch-card--primary">
  <div class="card-body">
    <div class="punch-status">正在进行</div>
    <div class="mt-2 font-weight-bold">07-31 13:38</div>
    <div class="punch-meta">
      <span><i class="la la-key"></i>密码</span>
      <span>14:08 结束</span>
    </div>
    <div class="punch-action">
      <form action="/student/punch/course/140242/5458535" method="post">
        <input name="pwd" type="text" placeholder="输入签到密码">
        <button type="submit">确 定</button>
      </form>
    </div>
  </div>
</div>
"""


def test_discovers_inline_password_form_as_password_checkin_item():
    items = parse_checkin_items(
        INLINE_PASSWORD_HTML,
        course_id="140242",
        module="punchs",
        response_url="https://bjmf.k8n.cn/student/course/140242/punchs",
    )

    assert len(items) == 1
    assert items[0].remote_item_id == "5458535"
    assert items[0].remote_module == "punch"
    assert items[0].mode_hint == "password"
    assert items[0].title == "密码"
    assert items[0].detail_url == ""


def test_inline_form_prevents_duplicate_detail_fetch_for_same_item():
    html = INLINE_PASSWORD_HTML + """
    <a href="/student/punch/course/140242/5458535">密码签到</a>
    """

    items = parse_checkin_items(
        html,
        course_id="140242",
        module="punchs",
        response_url="https://bjmf.k8n.cn/student/course/140242/punchs",
    )

    assert len(items) == 1
    assert items[0].detail_url == ""


def test_get_form_is_not_treated_as_submittable_checkin():
    html = INLINE_PASSWORD_HTML.replace('method="post"', 'method="get"')

    items = parse_checkin_items(
        html,
        course_id="140242",
        module="punchs",
        response_url="https://bjmf.k8n.cn/student/course/140242/punchs",
    )

    assert items == []


def test_inline_password_form_builds_password_only_submission():
    response_url = "https://bjmf.k8n.cn/student/course/140242/punchs"
    item = parse_checkin_items(
        INLINE_PASSWORD_HTML,
        course_id="140242",
        module="punchs",
        response_url=response_url,
    )[0]

    form = parse_checkin_form(INLINE_PASSWORD_HTML, response_url, item)
    fields = build_submission_fields(
        form,
        CheckinParameters(password="2468"),
        remote_item_id=item.remote_item_id,
    )

    assert form.action == (
        "https://bjmf.k8n.cn/student/punch/course/140242/5458535"
    )
    assert form.method == "post"
    assert form.mode == "password"
    assert form.password_field == "pwd"
    assert form.submit_capable is True
    assert fields == {"pwd": "2468"}


def test_existing_gps_qr_and_gps_photo_markers_keep_their_modes():
    html = """
    <a href="/student/punch_gps/course/140242/1001">GPS 签到</a>
    <a href="/student/punchcard/course/140242/1002">扫码签到</a>
    <button onclick="punch_gps_photo('1003')">
      GPS 拍照签到
      <input name="photo" type="file">
    </button>
    """

    items = parse_checkin_items(
        html,
        course_id="140242",
        module="punchs",
        response_url="https://bjmf.k8n.cn/student/course/140242/punchs",
    )

    assert [
        (item.remote_item_id, item.remote_module, item.mode_hint)
        for item in items
    ] == [
        ("1001", "punch_gps", "gps"),
        ("1002", "punchcard", "qr"),
        ("1003", "punch_gps", "gps_photo"),
    ]
