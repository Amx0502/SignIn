import re
from dataclasses import dataclass, replace
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag


PASSWORD_FIELD_ALIASES = {
    "password",
    "pwd",
    "code",
    "passcode",
}


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
    item_id_field: str = ""
    latitude_field: str = ""
    longitude_field: str = ""
    accuracy_field: str = ""
    gps_address_field: str = ""
    photo_resource_field: str = ""
    submit_capable: bool = False
    upload_action: str = ""
    upload_method: str = ""
    upload_file_field: str = ""
    upload_response_key: str = ""


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


def parse_student_name(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(
        "[data-student-name], #student-name, .student-name"
    )
    if isinstance(node, Tag):
        value = (
            _attribute_text(node.get("data-student-name"))
            or node.get_text(" ", strip=True)
        ).strip()
        if value:
            return value

    for script in soup.find_all("script"):
        source = script.string or script.get_text()
        config_match = re.search(
            r"\bvar\s+gconfig\s*=\s*\{(?P<body>.*?)\}\s*;?",
            source,
            re.DOTALL,
        )
        if not config_match:
            continue
        name_match = re.search(
            r"\buname\s*:\s*(['\"])(?P<name>.*?)\1",
            config_match.group("body"),
            re.DOTALL,
        )
        if name_match:
            return unescape(name_match.group("name")).strip()
    return ""


def parse_checkin_items(
    html: str,
    course_id: str,
    module: str,
    response_url: str,
) -> list[ParsedItem]:
    soup = BeautifulSoup(html, "html.parser")
    normalized_module = module.strip("/")
    items: list[ParsedItem] = []
    positions: dict[str, int] = {}

    def add_item(
        remote_item_id: str,
        *,
        title: str = "",
        remote_module: str = "",
        detail_url: str = "",
        mode_hint: str = "unknown",
    ) -> None:
        remote_item_id = unquote(remote_item_id).strip()
        if not remote_item_id:
            return
        if remote_item_id not in positions:
            positions[remote_item_id] = len(items)
            items.append(
                ParsedItem(
                    remote_item_id=remote_item_id,
                    course_id=course_id,
                    title=title,
                    remote_module=remote_module or normalized_module,
                    detail_url=detail_url,
                    mode_hint=mode_hint,
                )
            )
            return

        index = positions[remote_item_id]
        current = items[index]
        resolved_module = current.remote_module
        if (
            remote_module
            and current.remote_module == normalized_module
            and remote_module != normalized_module
        ):
            resolved_module = remote_module
        items[index] = replace(
            current,
            title=current.title or title,
            remote_module=resolved_module,
            detail_url=current.detail_url or detail_url,
            mode_hint=(
                current.mode_hint
                if current.mode_hint != "unknown"
                else mode_hint
            ),
        )

    for tag in soup.find_all(True):
        title = _item_title(tag)
        punchcard_id = _punchcard_item_id(tag)
        if punchcard_id:
            add_item(
                punchcard_id,
                title=title,
                mode_hint="qr",
            )

        gps_item_id = _gps_item_id(tag)
        if gps_item_id:
            add_item(
                gps_item_id,
                title=title,
                remote_module="punch_gps",
                mode_hint="gps",
            )

        if tag.name == "a" and tag.get("href"):
            href = _attribute_text(tag.get("href"))
            route = _checkin_route(href, course_id)
            if route:
                route_module, remote_item_id = route
                add_item(
                    remote_item_id,
                    title=title,
                    remote_module=route_module,
                    detail_url=urljoin(response_url, href),
                    mode_hint=_item_mode_hint(tag, route_module),
                )

    response_route = _checkin_route(response_url, course_id)
    if response_route:
        route_module, remote_item_id = response_route
        add_item(
            remote_item_id,
            title=_direct_item_title(soup),
            remote_module=route_module,
            detail_url=response_url,
            mode_hint=_module_mode_hint(route_module),
        )
    return items


def parse_checkin_form(
    html: str,
    response_url: str,
    item: ParsedItem,
) -> ParsedForm:
    soup = BeautifulSoup(html, "html.parser")
    form = _select_checkin_form(soup, response_url, item)
    inputs = form.find_all("input") if form else []

    hidden_fields = {
        _attribute_text(input_tag.get("name")): _attribute_text(
            input_tag.get("value")
        )
        for input_tag in inputs
        if input_tag.get("name")
        and _attribute_text(input_tag.get("type")).lower() == "hidden"
        and _attribute_text(
            input_tag.get("name")
        ).strip().lower() not in PASSWORD_FIELD_ALIASES
    }
    item_id_field = _first_named_field(
        inputs,
        {"id", "punch_id", "punchcard_id"},
    )
    latitude_field = _first_named_field(
        inputs,
        {"lat", "latitude"},
    )
    longitude_field = _first_named_field(
        inputs,
        {"lng", "lon", "longitude"},
    )
    accuracy_field = _first_named_field(
        inputs,
        {"acc", "accuracy"},
    )
    gps_address_field = _first_named_field(
        inputs,
        {"gps_addr", "address", "addr"},
    )
    password_field = _first_password_field(
        inputs,
        PASSWORD_FIELD_ALIASES,
    ) or _first_field_name(inputs, "password")
    file_field = _first_field_name(inputs, "file")
    photo_resource_field = _first_named_field(
        inputs,
        {"res", "resource", "resource_id", "photo_resource"},
    )
    has_gps_field = bool(latitude_field or longitude_field or accuracy_field)
    upload_action = ""
    upload_method = ""
    upload_file_field = ""
    upload_response_key = ""
    if isinstance(form, Tag):
        declared_upload_action = _attribute_text(
            form.get("data-upload-action")
        ).strip()
        declared_upload_file = _attribute_text(
            form.get("data-upload-file-field")
        ).strip()
        declared_response_key = _attribute_text(
            form.get("data-upload-response-key")
        ).strip()
        if (
            declared_upload_action
            and declared_upload_file
            and declared_response_key
        ):
            upload_action = urljoin(
                response_url,
                declared_upload_action,
            )
            upload_method = (
                _attribute_text(
                    form.get("data-upload-method")
                ).strip()
                or "post"
            ).lower()
            upload_file_field = declared_upload_file
            upload_response_key = declared_response_key

    if (
        has_gps_field
        and (
            file_field
            or photo_resource_field
            or (
                photo_resource_field
                and upload_action
                and upload_file_field
                and upload_response_key
            )
        )
    ):
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
    submit_capable = isinstance(form, Tag)
    if isinstance(form, Tag):
        action = urljoin(
            response_url,
            _attribute_text(form.get("action")) or response_url,
        )
        method = (
            _attribute_text(form.get("method")).strip()
            or "get"
        ).lower()
    else:
        synthetic = _synthetic_contract(
            soup,
            response_url,
            item,
        )
        if synthetic is not None:
            action, mode = synthetic
            method = "post"
            submit_capable = True
            item_id_field = "id"
            if mode == "gps":
                latitude_field = "lat"
                longitude_field = "lng"
                accuracy_field = "acc"
                gps_address_field = "gps_addr"

    if not submit_capable:
        method = "get"

    return ParsedForm(
        action=action,
        method=method.lower(),
        mode=mode,
        hidden_fields=hidden_fields,
        password_field=password_field,
        file_field=file_field,
        item_id_field=item_id_field,
        latitude_field=latitude_field,
        longitude_field=longitude_field,
        accuracy_field=accuracy_field,
        gps_address_field=gps_address_field,
        photo_resource_field=photo_resource_field,
        submit_capable=submit_capable,
        upload_action=upload_action,
        upload_method=upload_method,
        upload_file_field=upload_file_field,
        upload_response_key=upload_response_key,
    )


def _synthetic_contract(
    soup: BeautifulSoup,
    response_url: str,
    item: ParsedItem,
) -> tuple[str, str] | None:
    if _has_exact_gps_marker(soup, item):
        return (
            _canonical_submit_url(
                response_url,
                "punch_gps",
                item,
            ),
            "gps",
        )
    if _has_exact_punchcard_marker(soup, item):
        return (
            _canonical_submit_url(
                response_url,
                item.remote_module,
                item,
            ),
            "qr",
        )
    return None


def _canonical_submit_url(
    response_url: str,
    module: str,
    item: ParsedItem,
) -> str:
    normalized_module = module.lower()
    if not re.fullmatch(
        r"(?:punch\w+|daka)",
        normalized_module,
        re.ASCII,
    ):
        normalized_module = "punchs"
    return urljoin(
        response_url,
        (
            f"/student/{normalized_module}/course/"
            f"{quote(str(item.course_id), safe='')}/"
            f"{quote(str(item.remote_item_id), safe='')}"
        ),
    )


def _select_checkin_form(
    soup: BeautifulSoup,
    response_url: str,
    item: ParsedItem,
) -> Tag | None:
    container = soup.find(id=f"punchcard_{item.remote_item_id}")
    if isinstance(container, Tag):
        if container.name == "form" and _is_post_form(container):
            return container
        nested_form = container.find("form")
        if (
            isinstance(nested_form, Tag)
            and _is_post_form(nested_form)
        ):
            return nested_form

    forms = [
        form
        for form in soup.find_all("form")
        if _is_post_form(form)
    ]
    for form in forms:
        if _form_explicitly_targets_item(form, item):
            return form

    if item.detail_url:
        expected_url = urlparse(item.detail_url)
        for form in forms:
            action = _attribute_text(form.get("action"))
            actual_url = urlparse(urljoin(response_url, action))
            if (
                actual_url.netloc == expected_url.netloc
                and actual_url.path.rstrip("/")
                == expected_url.path.rstrip("/")
            ):
                return form

    expected_host = urlparse(
        item.detail_url or response_url
    ).netloc.lower()
    for form in forms:
        action = _attribute_text(form.get("action"))
        actual_url = urlparse(urljoin(response_url, action))
        route = _checkin_route(
            actual_url.geturl(),
            str(item.course_id),
        )
        if (
            actual_url.netloc.lower() == expected_host
            and route is not None
            and route[1] == str(item.remote_item_id)
        ):
            return form
    return None


def _form_explicitly_targets_item(
    form: Tag,
    item: ParsedItem,
) -> bool:
    expected_id = str(item.remote_item_id)
    return any(
        _attribute_text(form.get(attribute)).strip()
        == expected_id
        for attribute in (
            "data-checkin-item-id",
            "data-item-id",
            "item-id",
            "data-checkin",
        )
    )


def _is_post_form(form: Tag) -> bool:
    return (
        _attribute_text(form.get("method")).strip().lower()
        == "post"
    )


def parse_checkin_result(html: str, response_url: str) -> ParsedResult:
    soup = BeautifulSoup(html, "html.parser")
    message = " ".join(soup.get_text(" ", strip=True).split())

    if _is_login_page(soup, response_url, message):
        status = "cookie_expired"
    else:
        status = _structured_status(soup) or _result_node_status(soup)

    return ParsedResult(
        status=status or "unknown_result",
        message=message,
        response_url=response_url,
    )


def _attribute_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value) if value is not None else ""


def _item_title(tag: Tag) -> str:
    return _attribute_text(
        tag.get("data-title")
    ) or tag.get_text(" ", strip=True)


def _punchcard_item_id(tag: Tag) -> str:
    for attribute in ("id", "data-target", "data-id", "href"):
        value = _attribute_text(tag.get(attribute))
        match = re.search(
            r"(?:^|[#\s])punchcard_([A-Za-z0-9_.-]+)(?:$|[\s])",
            value,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return ""


def _gps_item_id(tag: Tag) -> str:
    for value in tag.attrs.values():
        match = re.search(
            r"\bpunch_gps\s*\(\s*['\"]?([^,'\"\s)]+)",
            _attribute_text(value),
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return ""


def _checkin_route(
    url: str,
    expected_course_id: str,
) -> tuple[str, str] | None:
    path = unquote(urlparse(url).path)
    match = re.fullmatch(
        r"/student/(punch\w+|daka)/course/([^/]+)/([^/]+)/?",
        path,
        re.IGNORECASE | re.ASCII,
    )
    if not match or match.group(2) != expected_course_id:
        return None
    return match.group(1), match.group(3)


def _module_mode_hint(module: str) -> str:
    lowered_module = module.lower()
    if "gps" in lowered_module:
        return "gps"
    if "punchcard" in lowered_module:
        return "qr"
    return "unknown"


def _item_mode_hint(tag: Tag, module: str) -> str:
    explicit_mode = _attribute_text(tag.get("data-mode"))
    if explicit_mode:
        return explicit_mode
    if _gps_item_id(tag):
        return "gps"
    if _punchcard_item_id(tag):
        return "qr"
    return _module_mode_hint(module)


def _direct_item_title(soup: BeautifulSoup) -> str:
    title = soup.select_one("#title, .punch-title, h1, h2")
    return title.get_text(" ", strip=True) if isinstance(title, Tag) else ""


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
    explicit_name = _attribute_text(anchor.get("data-course-name"))
    if explicit_name:
        return explicit_name

    name_parts: list[str] = []
    for text_node in anchor.find_all(string=True):
        text = str(text_node).strip()
        if not text:
            continue
        belongs_to_class_code = False
        for parent in text_node.parents:
            if parent is anchor:
                break
            if isinstance(parent, Tag) and (
                "class-code" in parent.get("class", [])
                or parent.has_attr("data-class-code")
            ):
                belongs_to_class_code = True
                break
        if not belongs_to_class_code:
            name_parts.append(text)
    return " ".join(name_parts)


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


def _first_named_field(
    inputs: list[Tag],
    aliases: set[str],
) -> str:
    for input_tag in inputs:
        name = _attribute_text(input_tag.get("name")).strip()
        if name.lower() in aliases:
            return name
    return ""


def _first_password_field(
    inputs: list[Tag],
    aliases: set[str],
) -> str:
    editable_types = {"", "text", "password", "tel", "number"}
    for input_tag in inputs:
        field_type = _attribute_text(
            input_tag.get("type")
        ).strip().lower()
        name = _attribute_text(
            input_tag.get("name")
        ).strip()
        if (
            field_type in editable_types
            and name.lower() in aliases
        ):
            return name
    return ""


def _has_exact_gps_marker(
    soup: BeautifulSoup,
    item: ParsedItem,
) -> bool:
    if item.remote_module.lower() != "punch_gps":
        return False
    expected_id = str(item.remote_item_id)
    return any(
        _gps_item_id(tag) == expected_id
        for tag in soup.find_all(True)
    )


def _has_exact_punchcard_marker(
    soup: BeautifulSoup,
    item: ParsedItem,
) -> bool:
    expected_id = str(item.remote_item_id)
    return any(
        _punchcard_item_id(tag) == expected_id
        for tag in soup.find_all(True)
    )


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


def _result_node_status(soup: BeautifulSoup) -> str:
    for node in soup.select(
        "#title, .punch-success-info, .punch-status"
    ):
        status = _status_from_text(node.get_text(" ", strip=True))
        if status:
            return status
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
