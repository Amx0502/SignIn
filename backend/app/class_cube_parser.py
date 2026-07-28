import re
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class ParsedCourse:
    remote_course_id: str
    name: str
    class_code: str = ""


@dataclass(frozen=True)
class ParsedItem:
    remote_item_id: str
    course_id: str
    title: str = ""
    remote_module: str = "punchs"
    detail_url: str = ""
    mode_hint: str = "unknown"


@dataclass(frozen=True)
class ParsedForm:
    action: str
    method: str
    mode: str
    hidden_fields: dict[str, str]
    password_field: str = ""
    file_field: str = ""


@dataclass(frozen=True)
class ParsedResult:
    status: str
    message: str = ""
    response_url: str = ""


def parse_qr_image_url(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for image in soup.find_all("img"):
        source = image.get("src") or image.get("data-src")
        if not isinstance(source, str) or not source:
            continue
        marker = " ".join(
            (
                _attribute_text(image.get("id")),
                _attribute_text(image.get("class")),
                _attribute_text(image.get("alt")),
                source,
            )
        ).lower()
        if "qr" in marker or "二维码" in marker:
            return urljoin(base_url, source)
    return ""


def parse_courses(html: str) -> list[ParsedCourse]:
    soup = BeautifulSoup(html, "html.parser")
    courses: list[ParsedCourse] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = _attribute_text(anchor.get("href"))
        course_id = _course_id(href)
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)
        courses.append(
            ParsedCourse(
                remote_course_id=course_id,
                name=_course_name(anchor),
                class_code=_class_code(anchor),
            )
        )
    return courses


def parse_checkin_items(
    html: str,
    course_id: str,
    module: str,
    response_url: str,
) -> list[ParsedItem]:
    soup = BeautifulSoup(html, "html.parser")
    normalized_module = module.strip("/")
    path_pattern = re.compile(
        rf"/student/{re.escape(normalized_module)}/course/"
        rf"{re.escape(course_id)}/([^/?#]+)/?$"
    )
    items: list[ParsedItem] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = _attribute_text(anchor.get("href"))
        match = path_pattern.search(urlparse(href).path)
        if not match:
            continue
        remote_item_id = unquote(match.group(1))
        if remote_item_id in seen:
            continue
        seen.add(remote_item_id)
        items.append(
            ParsedItem(
                remote_item_id=remote_item_id,
                course_id=course_id,
                title=_attribute_text(anchor.get("data-title"))
                or anchor.get_text(" ", strip=True),
                remote_module=normalized_module,
                detail_url=urljoin(response_url, href),
                mode_hint=_attribute_text(anchor.get("data-mode"))
                or "unknown",
            )
        )
    return items


def parse_checkin_form(
    html: str,
    response_url: str,
    item: ParsedItem,
) -> ParsedForm:
    del item
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    inputs = form.find_all("input") if form else soup.find_all("input")

    hidden_fields = {
        _attribute_text(input_tag.get("name")): _attribute_text(
            input_tag.get("value")
        )
        for input_tag in inputs
        if input_tag.get("name")
        and _attribute_text(input_tag.get("type")).lower() == "hidden"
    }
    password_field = _first_field_name(inputs, "password")
    file_field = _first_field_name(inputs, "file")
    field_names = {
        _attribute_text(input_tag.get("name")).lower()
        for input_tag in inputs
    }
    has_gps_field = bool(
        field_names
        & {"lat", "lng", "acc", "latitude", "longitude", "accuracy"}
    )

    if file_field and has_gps_field:
        mode = "gps_photo"
    elif password_field:
        mode = "password"
    elif has_gps_field:
        mode = "gps"
    elif _has_qr_marker(soup, html):
        mode = "qr"
    else:
        mode = "unknown"

    action = response_url
    method = "get"
    if isinstance(form, Tag):
        action = urljoin(
            response_url,
            _attribute_text(form.get("action")) or response_url,
        )
        method = _attribute_text(form.get("method")) or "get"

    return ParsedForm(
        action=action,
        method=method.lower(),
        mode=mode,
        hidden_fields=hidden_fields,
        password_field=password_field,
        file_field=file_field,
    )


def parse_checkin_result(html: str, response_url: str) -> ParsedResult:
    soup = BeautifulSoup(html, "html.parser")
    message = " ".join(soup.get_text(" ", strip=True).split())

    if _is_login_page(soup, response_url, message):
        status = "cookie_expired"
    else:
        status = _structured_status(soup) or _status_from_text(message)

    return ParsedResult(
        status=status or "unknown_result",
        message=message,
        response_url=response_url,
    )


def _attribute_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value) if value is not None else ""


def _course_id(href: str) -> str:
    match = re.search(
        r"/student/courses?/([^/?#]+)/?$",
        urlparse(href).path,
    )
    return unquote(match.group(1)) if match else ""


def _course_name(anchor: Tag) -> str:
    name_node = anchor.select_one(".course-name, [data-course-name]")
    if isinstance(name_node, Tag):
        return _attribute_text(
            name_node.get("data-course-name")
        ) or name_node.get_text(" ", strip=True)
    return _attribute_text(
        anchor.get("data-course-name")
    ) or anchor.get_text(" ", strip=True)


def _class_code(anchor: Tag) -> str:
    for attribute in ("data-class-code", "data-code"):
        value = _attribute_text(anchor.get(attribute))
        if value:
            return value.strip()
    code_node = anchor.select_one(".class-code, [data-class-code]")
    if isinstance(code_node, Tag):
        return (
            _attribute_text(code_node.get("data-class-code"))
            or code_node.get_text(" ", strip=True)
        ).strip()
    match = re.search(
        r"班级(?:码|代码)\s*[:：]\s*([^\s]+)",
        anchor.get_text(" ", strip=True),
    )
    return match.group(1) if match else ""


def _first_field_name(inputs: list[Tag], field_type: str) -> str:
    for input_tag in inputs:
        if _attribute_text(input_tag.get("type")).lower() == field_type:
            return _attribute_text(input_tag.get("name"))
    return ""


def _has_qr_marker(soup: BeautifulSoup, html: str) -> bool:
    if "punchcard_" in html.lower() or "二维码" in html:
        return True
    return bool(
        soup.find(
            attrs={"id": re.compile(r"(?:qr|qrcode)", re.IGNORECASE)}
        )
        or soup.find(
            class_=re.compile(r"(?:qr|qrcode)", re.IGNORECASE)
        )
    )


def _is_login_page(
    soup: BeautifulSoup,
    response_url: str,
    message: str,
) -> bool:
    response_path = urlparse(response_url).path.lower()
    if re.search(r"/(?:login|signin)(?:/|$)", response_path):
        return True

    for form in soup.find_all("form"):
        action_path = urlparse(
            _attribute_text(form.get("action"))
        ).path.lower()
        has_password = form.find("input", attrs={"type": "password"})
        if has_password and re.search(
            r"/(?:login|signin)(?:/|$)", action_path
        ):
            return True

    return bool(
        ("请先登录" in message or "登录后" in message)
        and soup.find("input", attrs={"type": "password"})
    )


def _structured_status(soup: BeautifulSoup) -> str:
    aliases = {
        "success": "success",
        "ok": "success",
        "signed": "success",
        "already_signed": "already_signed",
        "already-signed": "already_signed",
        "not_started": "not_started",
        "not-started": "not_started",
    }
    for tag in soup.find_all(True):
        for attribute in ("data-status", "data-result", "data-state"):
            value = _attribute_text(tag.get(attribute)).strip().lower()
            if value in aliases:
                return aliases[value]
    return ""


def _status_from_text(message: str) -> str:
    if "尚未开始" in message or "未开始" in message:
        return "not_started"
    if (
        "已经签到" in message
        or "已签到" in message
        or "请勿重复签到" in message
    ):
        return "already_signed"
    if "签到成功" in message or "打卡成功" in message:
        return "success"
    return ""
