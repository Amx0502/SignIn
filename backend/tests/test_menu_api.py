import asyncio

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.menu_events import MenuEventBroker, format_version_event
from app.menu_repository import MenuVersionConflictError
from app.menu_router import create_menu_guard, create_menu_router


class FakeMenuRepository:
    def __init__(self):
        self.version = 4
        self.visible = True
        self.visible_keys = set()
        self.last_global_update = None

    def effective_catalog(self, user):
        return {
            "version": self.version,
            "menus": [{
                "key": "xxqd",
                "title": "小小签到",
                "path": None,
                "icon": "xxqd",
                "children": [],
            }],
        }

    def admin_config(self, user_id=None):
        return {
            "version": self.version,
            "catalog": [],
            "global": {},
            "user_id": user_id,
            "overrides": {},
        }

    def update_global(self, **kwargs):
        self.last_global_update = kwargs
        if kwargs["expected_version"] != self.version:
            raise MenuVersionConflictError(self.version)
        self.version += 1
        return {"version": self.version, "visibility": kwargs["visibility"]}

    def update_user_overrides(self, **kwargs):
        self.version += 1
        return {"version": self.version, "overrides": kwargs["overrides"]}

    def list_audit_logs(self, limit=100):
        return []

    def is_menu_visible(self, user, menu_key):
        return user["role"] == "admin" or self.visible or menu_key in self.visible_keys


def build_app(role="user"):
    app = FastAPI()
    repository = FakeMenuRepository()
    broker = MenuEventBroker()

    def current_user():
        return {"id": 1 if role == "admin" else 2, "role": role}

    def admin_user(user=Depends(current_user)):
        if user["role"] != "admin":
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="需要管理员权限")
        return user

    get_repository = lambda: repository
    app.include_router(
        create_menu_router(current_user, admin_user, get_repository, broker)
    )
    menu_guard = create_menu_guard(current_user, get_repository)

    @app.get("/protected")
    def protected(user=Depends(menu_guard("xxqd.overview"))):
        return {"user_id": user["id"]}

    return app, repository, broker


def test_authenticated_user_receives_effective_menu_catalog():
    app, _, _ = build_app()
    response = TestClient(app).get("/api/menu/catalog")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == 4
    assert response.json()["data"]["menus"][0]["key"] == "xxqd"


def test_non_admin_cannot_open_menu_management_api():
    app, _, _ = build_app(role="user")
    response = TestClient(app).get("/api/admin/menu-config")
    assert response.status_code == 403


def test_stale_admin_save_returns_409_with_current_version():
    app, _, _ = build_app(role="admin")
    response = TestClient(app).put(
        "/api/admin/menu-config/global",
        json={"version": 3, "visibility": {"xxqd.overview": False}},
    )
    assert response.status_code == 409
    assert response.json() == {
        "ok": False,
        "error": "菜单配置已被其他管理员修改，请刷新后重试",
        "current_version": 4,
    }


def test_successful_save_publishes_new_version():
    app, repository, broker = build_app(role="admin")
    published = []

    async def capture(version):
        published.append(version)

    broker.publish = capture
    response = TestClient(app).put(
        "/api/admin/menu-config/global",
        json={"version": 4, "visibility": {"xxqd.overview": False}},
    )
    assert response.status_code == 200
    assert repository.last_global_update == {
        "expected_version": 4,
        "visibility": {"xxqd.overview": False},
        "actor_user_id": 1,
    }
    assert published == [5]


def test_hidden_menu_guard_blocks_ordinary_user_but_not_admin():
    app, repository, _ = build_app(role="user")
    repository.visible = False
    response = TestClient(app).get("/protected")
    assert response.status_code == 403
    assert response.json()["detail"]["menu_key"] == "xxqd.overview"

    admin_app, admin_repository, _ = build_app(role="admin")
    admin_repository.visible = False
    assert TestClient(admin_app).get("/protected").status_code == 200


def test_menu_guard_can_allow_shared_read_api_when_any_consumer_is_visible():
    app, repository, _ = build_app(role="user")
    repository.visible = False
    repository.visible_keys = {"class_cube.overview"}

    def current_user():
        return {"id": 2, "role": "user"}

    menu_guard = create_menu_guard(current_user, lambda: repository)

    @app.get("/shared-read")
    def shared_read(
        user=Depends(menu_guard(("class_cube.overview", "class_cube.accounts"))),
    ):
        return {"user_id": user["id"]}

    assert TestClient(app).get("/shared-read").status_code == 200


def test_sse_broker_notifies_waiting_clients_with_version_event():
    async def scenario():
        broker = MenuEventBroker()
        stream = broker.subscribe(last_version=1, heartbeat_seconds=1)
        pending = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        await broker.publish(2)
        event = await asyncio.wait_for(pending, timeout=1)
        await stream.aclose()
        return event

    assert asyncio.run(scenario()) == format_version_event(2)
    assert format_version_event(7) == 'event: version\ndata: {"version":7}\n\n'


def test_main_application_serves_menu_router_and_enforces_business_guard(
    monkeypatch,
):
    import app.main as main

    repository = FakeMenuRepository()
    repository.visible = False
    monkeypatch.setattr(main, "menu_repository", repository)
    main.app.dependency_overrides[main.get_current_user] = lambda: {
        "id": 2,
        "role": "user",
    }
    try:
        client = TestClient(main.app)
        catalog = client.get("/api/menu/catalog")
        protected = client.get("/api/xxqd/logs")
    finally:
        main.app.dependency_overrides.clear()

    assert catalog.status_code == 200
    assert catalog.json()["data"]["version"] == 4
    assert protected.status_code == 403
    assert protected.json()["menu_key"] == "xxqd.logs"
