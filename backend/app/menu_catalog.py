from typing import Any


MENU_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "key": "xxqd",
        "title": "小小签到",
        "path": None,
        "parent_key": None,
        "icon": "xxqd",
        "order": 10,
    },
    {
        "key": "xxqd.overview",
        "title": "系统概览",
        "path": "/overview",
        "parent_key": "xxqd",
        "icon": "Odometer",
        "order": 11,
    },
    {
        "key": "xxqd.accounts",
        "title": "账号管理",
        "path": "/accounts",
        "parent_key": "xxqd",
        "icon": "User",
        "order": 12,
    },
    {
        "key": "xxqd.auto",
        "title": "自动签到",
        "path": "/checkin/auto",
        "parent_key": "xxqd",
        "icon": "Timer",
        "order": 13,
    },
    {
        "key": "xxqd.tasks",
        "title": "任务管理",
        "path": "/tasks",
        "parent_key": "xxqd",
        "icon": "List",
        "order": 14,
    },
    {
        "key": "xxqd.logs",
        "title": "运行日志",
        "path": "/logs",
        "parent_key": "xxqd",
        "icon": "Document",
        "order": 15,
    },
    {
        "key": "class_cube",
        "title": "班级魔方",
        "path": None,
        "parent_key": None,
        "icon": "class_cube",
        "order": 20,
    },
    {
        "key": "class_cube.overview",
        "title": "系统概览",
        "path": "/class-cube/overview",
        "parent_key": "class_cube",
        "icon": "Odometer",
        "order": 21,
    },
    {
        "key": "class_cube.accounts",
        "title": "账号管理",
        "path": "/class-cube/accounts",
        "parent_key": "class_cube",
        "icon": "User",
        "order": 22,
    },
    {
        "key": "class_cube.tasks",
        "title": "自动任务",
        "path": "/class-cube/tasks",
        "parent_key": "class_cube",
        "icon": "Timer",
        "order": 23,
    },
    {
        "key": "class_cube.runs",
        "title": "运行记录",
        "path": "/class-cube/runs",
        "parent_key": "class_cube",
        "icon": "Document",
        "order": 24,
    },
    {
        "key": "class_cube.logs",
        "title": "魔方日志",
        "path": "/class-cube/logs",
        "parent_key": "class_cube",
        "icon": "Document",
        "order": 25,
    },
    {
        "key": "miaoying",
        "title": "秒应",
        "path": "/miaoying",
        "parent_key": None,
        "icon": "miaoying",
        "order": 30,
    },
)

MENU_BY_KEY = {item["key"]: item for item in MENU_CATALOG}
MENU_KEYS = frozenset(MENU_BY_KEY)


def build_effective_menu(
    global_visibility: dict[str, bool],
    overrides: dict[str, bool],
    is_admin: bool,
) -> list[dict[str, Any]]:
    direct_visibility = {
        key: True if is_admin else overrides.get(key, global_visibility.get(key, True))
        for key in MENU_KEYS
    }
    source_children: dict[str | None, list[dict[str, Any]]] = {}
    for item in sorted(MENU_CATALOG, key=lambda row: row["order"]):
        source_children.setdefault(item["parent_key"], []).append(item)

    def render(parent_key: str | None, ancestors_visible: bool) -> list[dict[str, Any]]:
        rendered_items = []
        for item in source_children.get(parent_key, []):
            visible = ancestors_visible and direct_visibility[item["key"]]
            if not visible:
                continue
            rendered_items.append({
                "key": item["key"],
                "title": item["title"],
                "path": item["path"],
                "icon": item["icon"],
                "children": render(item["key"], visible),
            })
        return rendered_items

    return render(None, True)


def visible_menu_keys(menus: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for item in menus:
        keys.add(item["key"])
        keys.update(visible_menu_keys(item.get("children") or []))
    return keys


def catalog_tree() -> list[dict[str, Any]]:
    return build_effective_menu({}, {}, True)
