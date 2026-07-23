from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import AuthService
from app.auth_database import AuthDatabase, AuthDatabaseSettings
from app.auth_repository import AuthRepository
from app.database import Database
from app.repository import AccountRepository
from app.service import AppState


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_user_management_api_enforces_roles_and_has_no_email(
    mysql_settings, monkeypatch, tmp_path
):
    from app import main

    business_database = Database(mysql_settings)
    business_database.initialize()
    auth_settings = AuthDatabaseSettings(
        host=mysql_settings.host,
        port=mysql_settings.port,
        name=mysql_settings.name.replace("xxqd_test_", "user_test_"),
        user=mysql_settings.user,
        password=mysql_settings.password,
    )
    auth_database = AuthDatabase(auth_settings)
    auth_database.initialize()
    auth_repository = AuthRepository(auth_database)
    auth_repository.initialize_users(tmp_path / "missing-users.json")

    state = AppState(
        repository=AccountRepository(business_database), start_scheduler=False
    )
    monkeypatch.setattr(main, "app_state", state)
    monkeypatch.setattr(main, "auth_service", AuthService(auth_repository))
    monkeypatch.setattr(
        main.config, "LEGACY_ACCOUNTS_FILE", tmp_path / "missing-accounts.json"
    )

    try:
        with TestClient(main.app) as client:
            login = client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "admin123",
                    "remember_me": False,
                },
            ).json()["data"]
            token = login["access_token"]
            assert "email" not in login["user"]

            blocked = client.get("/api/users", headers=_headers(token))
            assert blocked.status_code == 401

            changed = client.post(
                "/api/auth/change-password",
                headers=_headers(token),
                json={
                    "current_password": "admin123",
                    "new_password": "admin456",
                },
            )
            assert changed.status_code == 200

            users = client.get("/api/users", headers=_headers(token))
            assert users.status_code == 200
            assert "email" not in users.text

            created = client.post(
                "/api/users",
                headers=_headers(token),
                json={
                    "username": "worker",
                    "password": "worker123",
                    "role": "user",
                    "is_active": True,
                },
            )
            assert created.status_code == 200
            worker_id = created.json()["data"]["id"]

            worker_login = client.post(
                "/api/auth/login",
                json={
                    "username": "worker",
                    "password": "worker123",
                    "remember_me": False,
                },
            ).json()["data"]
            worker_token = worker_login["access_token"]
            client.post(
                "/api/auth/change-password",
                headers=_headers(worker_token),
                json={
                    "current_password": "worker123",
                    "new_password": "worker456",
                },
            )
            assert (
                client.get("/api/users", headers=_headers(worker_token)).status_code
                == 403
            )

            reset = client.post(
                f"/api/users/{worker_id}/reset-password",
                headers=_headers(token),
                json={"new_password": "reset123"},
            )
            assert reset.status_code == 200
            assert (
                client.get("/api/state", headers=_headers(worker_token)).status_code
                == 401
            )

            admin_id = users.json()["data"][0]["id"]
            protected = client.put(
                f"/api/users/{admin_id}",
                headers=_headers(token),
                json={"username": "admin", "role": "user", "is_active": True},
            )
            assert protected.status_code == 400
    finally:
        business_database.dispose()
        auth_database.drop_database_for_test()
