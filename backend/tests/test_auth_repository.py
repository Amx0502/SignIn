import hashlib
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, select, text

from app.auth_database import AuthDatabase, AuthDatabaseSettings
from app.auth_models import UserSessionRow
from app.auth_repository import (
    AuthRepository,
    LastAdminError,
    hash_password,
    verify_password,
)
from app.auth import AuthService
from app.models import LoginRequest


@pytest.fixture
def auth_database(mysql_settings):
    settings = AuthDatabaseSettings(
        host=mysql_settings.host,
        port=mysql_settings.port,
        name=mysql_settings.name.replace("xxqd_test_", "user_test_"),
        user=mysql_settings.user,
        password=mysql_settings.password,
    )
    database = AuthDatabase(settings)
    database.initialize()
    try:
        yield database
    finally:
        database.drop_database_for_test()


@pytest.fixture
def repository(auth_database):
    return AuthRepository(auth_database)


def test_auth_database_creates_only_auth_tables(auth_database):
    assert set(inspect(auth_database.engine).get_table_names()) == {
        "users",
        "user_sessions",
    }


def test_auth_database_removes_legacy_must_change_password_column(auth_database):
    with auth_database.engine.begin() as connection:
        if "must_change_password" not in {
            column["name"] for column in inspect(connection).get_columns("users")
        }:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN must_change_password "
                    "BOOLEAN NOT NULL DEFAULT 1"
                )
            )

    auth_database.dispose()
    auth_database.initialize()

    assert "must_change_password" not in {
        column["name"] for column in inspect(auth_database.engine).get_columns("users")
    }


def test_pbkdf2_password_round_trip():
    encoded = hash_password("secret123")
    assert verify_password("secret123", encoded) == (True, False)
    assert verify_password("wrong", encoded) == (False, False)


def test_empty_database_creates_default_admin(repository, tmp_path):
    assert repository.initialize_users(tmp_path / "missing.json") == 1
    users = repository.list_users()
    assert users[0]["username"] == "admin"
    assert users[0]["role"] == "admin"
    assert "must_change_password" not in users[0]
    assert "email" not in users[0]
    assert repository.initialize_users(tmp_path / "missing.json") == 0


def test_legacy_users_import_ignores_email(repository, tmp_path):
    old_digest = hashlib.sha256("admin123salt1234".encode()).hexdigest()
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            {
                "legacy": {
                    "username": "legacy",
                    "email": "ignored@example.com",
                    "password_hash": f"{old_digest}:salt1234",
                    "is_active": True,
                }
            }
        ),
        encoding="utf-8",
    )
    assert repository.initialize_users(path) == 1
    assert repository.list_users()[0]["username"] == "legacy"
    assert "email" not in repository.list_users()[0]


def test_user_crud_and_last_admin_protection(repository, tmp_path):
    repository.initialize_users(tmp_path / "missing.json")
    admin = repository.find_by_username("admin")
    user = repository.create_user("worker", "secret123", "user", True)
    assert repository.update_user(user["id"], "worker2", "user", False)["is_active"] is False
    repository.reset_password(user["id"], "newsecret")
    assert verify_password(
        "newsecret", repository.find_by_username("worker2").password_hash
    )[0]
    repository.delete_user(user["id"], actor_user_id=admin.id)
    with pytest.raises(LastAdminError):
        repository.update_user(admin.id, "admin", "user", True)


def test_session_stores_only_hash_and_expires(repository, auth_database, tmp_path):
    repository.initialize_users(tmp_path / "missing.json")
    user = repository.find_by_username("admin")
    token, expires_at = repository.create_session(user.id, "127.0.0.1", 60)
    assert repository.verify_session(token)["username"] == "admin"
    with auth_database.session() as session:
        row = session.scalar(select(UserSessionRow))
        assert row.token_hash != token
        row.expires_at = datetime.now() - timedelta(seconds=1)
    assert repository.verify_session(token) is None


def test_auth_service_login_logout_without_forced_change(repository, tmp_path):
    repository.initialize_users(tmp_path / "missing.json")
    service = AuthService(repository)
    ok, result = service.login(
        LoginRequest(username="admin", password="admin123", remember_me=False),
        "127.0.0.1",
    )
    assert ok is True
    assert result["user"]["role"] == "admin"
    assert "must_change_password" not in result["user"]
    assert "email" not in result["user"]
    user = service.verify_token(result["access_token"])
    assert user["username"] == "admin"
    service.logout(result["access_token"])
    assert service.verify_token(result["access_token"]) is None


def test_auth_service_has_single_token_verification_entrypoint(repository):
    service = AuthService(repository)

    assert not hasattr(service, "verify_token_allow_password_change")
