import importlib
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import Database
from app.repository import AccountRepository
from app.service import AppState


def test_importing_main_does_not_require_database_connection(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    sys.modules.pop("app.main", None)

    module = importlib.import_module("app.main")

    assert module.app.title


def test_account_and_task_api_contract_is_preserved(
    mysql_settings, monkeypatch, tmp_path
):
    monkeypatch.setenv("DB_PASSWORD", mysql_settings.password)
    module = importlib.import_module("app.main")
    database = Database(mysql_settings)
    database.initialize()
    state = AppState(repository=AccountRepository(database), start_scheduler=False)
    monkeypatch.setattr(module, "app_state", state)
    monkeypatch.setattr(
        module.config, "LEGACY_ACCOUNTS_FILE", tmp_path / "missing-accounts.json"
    )
    monkeypatch.setattr(
        module.auth_service,
        "verify_token",
        lambda token: SimpleNamespace(username="admin"),
    )
    headers = {"Authorization": "Bearer test"}

    try:
        with TestClient(module.app) as client:
            create = client.post(
                "/api/accounts",
                headers=headers,
                json={
                    "name": "A",
                    "mobile": "13800000000",
                    "password": "secret",
                    "token": "",
                },
            )
            assert create.status_code == 200
            assert create.json()["ok"] is True
            assert create.json()["data"]["tasks"] == []

            duplicate = client.post(
                "/api/accounts",
                headers=headers,
                json={
                    "name": "duplicate",
                    "mobile": "13800000000",
                    "password": "secret",
                    "token": "",
                },
            )
            assert duplicate.status_code == 400
            assert "sql" not in duplicate.text.lower()

            task = client.post(
                "/api/accounts/0/tasks",
                headers=headers,
                json={"index": 1, "title": "task", "times": ["08:00:00"]},
            )
            assert task.status_code == 200
            assert task.json()["data"]["title"] == "task"

            state_response = client.get("/api/state", headers=headers)
            assert state_response.json()["data"]["account_count"] == 1
            assert state_response.json()["data"]["task_count"] == 1

            assert (
                client.delete("/api/accounts/0/tasks/0", headers=headers).status_code
                == 200
            )
            assert client.delete("/api/accounts/0", headers=headers).status_code == 200
    finally:
        database.dispose()
