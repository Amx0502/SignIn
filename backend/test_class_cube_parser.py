import unittest
from dataclasses import FrozenInstanceError

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


class ClassCubeParserTest(unittest.TestCase):
    def setUp(self):
        self.item = ParsedItem(
            remote_item_id="12",
            course_id="1",
            title="晨间签到",
            remote_module="punchs",
            detail_url="https://bjmf.k8n.cn/student/punchs/course/1/12",
        )

    def test_resolves_qr_image_url(self):
        html = (
            '<main><img alt="课程二维码" class="qrcode" '
            'src="/uploads/qr/course-1.png"></main>'
        )

        actual = parse_qr_image_url(
            html, "https://bjmf.k8n.cn/student/course/1"
        )

        self.assertEqual(
            actual, "https://bjmf.k8n.cn/uploads/qr/course-1.png"
        )

    def test_parses_all_course_links_in_page_order_and_deduplicates(self):
        html = """
        <section id="first-page">
          <a href="/student/course/101" data-class-code="MATH-A">
            高等数学
          </a>
          <a href="/student/course/202">大学英语</a>
        </section>
        <section id="later-page">
          <a href="/student/course/101">重复的高等数学</a>
          <a href="https://bjmf.k8n.cn/student/courses/303"
             data-class-code="PHYS-C">大学物理</a>
        </section>
        """

        actual = parse_courses(html)

        self.assertEqual(
            actual,
            [
                ParsedCourse("101", "高等数学", "MATH-A"),
                ParsedCourse("202", "大学英语"),
                ParsedCourse("303", "大学物理", "PHYS-C"),
            ],
        )

    def test_parses_checkin_items_in_page_order_and_deduplicates(self):
        html = """
        <a href="/student/punchs/course/1/12"
           data-mode="qr">晨间签到</a>
        <a href="/student/punchs/course/1/13">晚间签到</a>
        <a href="/student/punchs/course/1/12">重复签到</a>
        <a href="/student/homework/course/1/99">不是当前模块</a>
        """

        actual = parse_checkin_items(
            html,
            course_id="1",
            module="punchs",
            response_url="https://bjmf.k8n.cn/student/punchs/course/1",
        )

        self.assertEqual(
            actual,
            [
                ParsedItem(
                    remote_item_id="12",
                    course_id="1",
                    title="晨间签到",
                    remote_module="punchs",
                    detail_url=(
                        "https://bjmf.k8n.cn/student/punchs/course/1/12"
                    ),
                    mode_hint="qr",
                ),
                ParsedItem(
                    remote_item_id="13",
                    course_id="1",
                    title="晚间签到",
                    remote_module="punchs",
                    detail_url=(
                        "https://bjmf.k8n.cn/student/punchs/course/1/13"
                    ),
                ),
            ],
        )

    def test_detects_four_modes(self):
        cases = {
            "qr": (
                '<div id="punchcard_12"><form '
                'action="/student/punchs/course/1/12"></form></div>'
            ),
            "gps": (
                '<form><input name="lat"><input name="lng">'
                '<input name="acc"></form>'
            ),
            "gps_photo": (
                '<form><input name="lat">'
                '<input type="file" name="photo"></form>'
            ),
            "password": (
                '<form><input type="password" name="passcode"></form>'
            ),
        }
        for expected, html in cases.items():
            with self.subTest(expected):
                form = parse_checkin_form(
                    html, "https://bjmf.k8n.cn/item", self.item
                )
                self.assertEqual(form.mode, expected)

    def test_mode_priority_prefers_gps_photo_over_password(self):
        html = """
        <form>
          <input name="lat">
          <input name="lng">
          <input type="file" name="photo">
          <input type="password" name="passcode">
        </form>
        """

        form = parse_checkin_form(
            html, "https://bjmf.k8n.cn/item", self.item
        )

        self.assertEqual(form.mode, "gps_photo")

    def test_parses_form_action_method_and_fields(self):
        html = """
        <form action="../submit/12" method="POST">
          <input type="hidden" name="_token" value="redacted-token">
          <input type="hidden" name="course_id" value="1">
          <input type="password" name="passcode">
          <input type="file" name="proof">
        </form>
        """

        form = parse_checkin_form(
            html, "https://bjmf.k8n.cn/student/item/12", self.item
        )

        self.assertEqual(
            form,
            ParsedForm(
                action="https://bjmf.k8n.cn/student/submit/12",
                method="post",
                mode="password",
                hidden_fields={
                    "_token": "redacted-token",
                    "course_id": "1",
                },
                password_field="passcode",
                file_field="proof",
            ),
        )

    def test_detects_explicit_result_statuses(self):
        cases = {
            "success": '<div class="alert-success">签到成功</div>',
            "already_signed": "<main>您已签到，请勿重复提交</main>",
            "not_started": "<p>本次签到尚未开始</p>",
        }
        for expected, html in cases.items():
            with self.subTest(expected):
                result = parse_checkin_result(
                    html, "https://bjmf.k8n.cn/result"
                )
                self.assertEqual(result.status, expected)
                self.assertEqual(
                    result.response_url,
                    "https://bjmf.k8n.cn/result",
                )

    def test_accepts_structured_result_status(self):
        result = parse_checkin_result(
            '<div data-status="success">请求已经处理</div>',
            "https://bjmf.k8n.cn/result",
        )

        self.assertEqual(
            result,
            ParsedResult(
                status="success",
                message="请求已经处理",
                response_url="https://bjmf.k8n.cn/result",
            ),
        )

    def test_detects_login_page_as_expired_cookie(self):
        html = """
        <html>
          <form action="/student/login">
            <input name="account">
            <input type="password" name="password">
          </form>
        </html>
        """

        result = parse_checkin_result(
            html, "https://bjmf.k8n.cn/student/login"
        )

        self.assertEqual(result.status, "cookie_expired")

    def test_does_not_treat_plain_http_200_page_as_success(self):
        result = parse_checkin_result(
            "<html><body>处理中</body></html>",
            "https://bjmf.k8n.cn/x",
        )

        self.assertEqual(result.status, "unknown_result")

    def test_parser_records_are_immutable(self):
        records = [
            ParsedCourse("1", "课程"),
            self.item,
            ParsedForm("", "get", "unknown", {}),
            ParsedResult("unknown_result"),
        ]

        for record in records:
            with self.subTest(type(record).__name__):
                with self.assertRaises(FrozenInstanceError):
                    record.status = "changed"


if __name__ == "__main__":
    unittest.main()
