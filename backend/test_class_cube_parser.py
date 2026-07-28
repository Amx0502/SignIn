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
    parse_student_name,
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

    def test_excludes_class_code_node_from_course_name(self):
        html = """
        <a href="/student/course/404">
          <span>数据结构</span>
          <small class="class-code">CLASS-404</small>
        </a>
        """

        actual = parse_courses(html)

        self.assertEqual(
            actual,
            [ParsedCourse("404", "数据结构", "CLASS-404")],
        )

    def test_parses_student_name_from_strict_gconfig_or_named_node(self):
        cases = (
            (
                "<script>var gconfig={uid:'7',uname:'张同学',"
                "cname:'软件工程'};</script>",
                "张同学",
            ),
            (
                '<span data-student-name="李同学">个人中心</span>',
                "李同学",
            ),
        )

        for html, expected in cases:
            with self.subTest(expected):
                self.assertEqual(parse_student_name(html), expected)

    def test_student_name_does_not_use_unrelated_page_text(self):
        html = (
            "<main>用户名：不应猜测</main>"
            "<script>var other={uname:'也不应读取'};</script>"
        )

        self.assertEqual(parse_student_name(html), "")

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

    def test_parses_item_markers_and_exact_routes_in_first_seen_order(self):
        html = """
        <section id="punchcard_21">
          <button>二维码签到</button>
        </section>
        <button onclick="punch_gps(22)">GPS 签到</button>
        <a href="/student/punch_gps/course/1/22">GPS 详情</a>
        <a href="/student/daka/course/1/23">日常打卡</a>
        <a href="/student/punchs/course/1/21">重复二维码签到</a>
        <a href="/student/punchs/course/10/88">其他课程</a>
        <a href="/student/homework/course/1/99">非签到模块</a>
        """

        actual = parse_checkin_items(
            html,
            course_id="1",
            module="punchs",
            response_url="https://bjmf.k8n.cn/student/punchs/course/1",
        )

        self.assertEqual(
            [
                (
                    item.remote_item_id,
                    item.remote_module,
                    item.mode_hint,
                )
                for item in actual
            ],
            [
                ("21", "punchs", "qr"),
                ("22", "punch_gps", "gps"),
                ("23", "daka", "unknown"),
            ],
        )
        self.assertEqual(
            actual[0].detail_url,
            "https://bjmf.k8n.cn/student/punchs/course/1/21",
        )
        self.assertEqual(
            actual[1].detail_url,
            "https://bjmf.k8n.cn/student/punch_gps/course/1/22",
        )

    def test_parses_item_from_direct_response_url(self):
        actual = parse_checkin_items(
            '<h1 id="title">直接进入的签到</h1>',
            course_id="1",
            module="punchs",
            response_url=(
                "https://bjmf.k8n.cn/student/daka/course/1/77"
                "?from=notice"
            ),
        )

        self.assertEqual(
            actual,
            [
                ParsedItem(
                    remote_item_id="77",
                    course_id="1",
                    title="直接进入的签到",
                    remote_module="daka",
                    detail_url=(
                        "https://bjmf.k8n.cn/student/daka/course/1/77"
                        "?from=notice"
                    ),
                )
            ],
        )

    def test_detects_four_modes(self):
        cases = {
            "qr": (
                '<div id="punchcard_12"><form '
                'action="/student/punchs/course/1/12"></form></div>'
            ),
            "gps": (
                '<form action="/student/punch_gps/course/1/12" '
                'method="post">'
                '<input name="lat"><input name="lng">'
                '<input name="acc"></form>'
            ),
            "gps_photo": (
                '<form action="/student/punch_gps/course/1/12" '
                'method="post">'
                '<input name="lat">'
                '<input type="file" name="photo"></form>'
            ),
            "password": (
                '<form action="/student/daka/course/1/12" '
                'method="post">'
                '<input type="password" name="passcode"></form>'
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
        <form action="/student/punch_gps/course/1/12"
              method="post">
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
        <form action="/student/punchs/course/1/12" method="POST">
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
                action=(
                    "https://bjmf.k8n.cn/student/punchs/course/1/12"
                ),
                method="post",
                mode="password",
                hidden_fields={
                    "_token": "redacted-token",
                    "course_id": "1",
                },
                password_field="passcode",
                file_field="proof",
                submit_capable=True,
            ),
        )

    def test_selects_requested_item_form_after_navigation_form(self):
        html = """
        <form action="/student/search" method="get">
          <input name="keyword">
        </form>
        <section id="punchcard_12">
          <form action="/student/punchs/course/1/12" method="POST">
            <input type="hidden" name="_token" value="item-token">
            <input type="password" name="passcode">
          </form>
        </section>
        """

        form = parse_checkin_form(
            html,
            "https://bjmf.k8n.cn/student/punchs/course/1/12",
            self.item,
        )

        self.assertEqual(
            form,
            ParsedForm(
                action=(
                    "https://bjmf.k8n.cn/student/punchs/course/1/12"
                ),
                method="post",
                mode="password",
                hidden_fields={"_token": "item-token"},
                password_field="passcode",
                submit_capable=True,
            ),
        )

    def test_detects_explicit_result_statuses(self):
        cases = {
            "success": (
                '<div class="punch-success-info">签到成功</div>'
            ),
            "already_signed": (
                '<h1 id="title">您已签到，请勿重复提交</h1>'
            ),
            "not_started": (
                '<p class="punch-status">本次签到尚未开始</p>'
            ),
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

    def test_ignores_success_words_outside_result_nodes(self):
        html = """
        <aside class="help">
          提交完成后，页面将显示“签到成功”。
        </aside>
        <main>当前请求仍在处理中</main>
        """

        result = parse_checkin_result(
            html, "https://bjmf.k8n.cn/result"
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
