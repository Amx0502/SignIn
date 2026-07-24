import json

import pytest

from app.database_config import load_database_config


def valid_config():
    return {
        "business": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "xxqd",
            "user": "root",
            "password": "123456",
        },
        "auth": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "User",
            "user": "root",
            "password": "123456",
        },
    }


def write_config(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_loads_business_and_auth_database_settings(tmp_path):
    path = tmp_path / "database_config.json"
    write_config(path, valid_config())

    config = load_database_config(path)

    assert config.business.name == "xxqd"
    assert config.business.password == "123456"
    assert config.auth.name == "User"
    assert config.auth.port == 3306


def test_reports_missing_config_file(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(RuntimeError, match="数据库配置文件不存在") as exc_info:
        load_database_config(path)

    assert str(path) in str(exc_info.value)


def test_reports_invalid_json(tmp_path):
    path = tmp_path / "database_config.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError, match="JSON 格式错误"):
        load_database_config(path)


@pytest.mark.parametrize("section", ["business", "auth"])
def test_requires_both_database_sections(tmp_path, section):
    path = tmp_path / "database_config.json"
    data = valid_config()
    del data[section]
    write_config(path, data)

    with pytest.raises(RuntimeError, match=f"缺少配置段 {section}"):
        load_database_config(path)


def test_requires_all_connection_fields(tmp_path):
    path = tmp_path / "database_config.json"
    data = valid_config()
    del data["business"]["password"]
    write_config(path, data)

    with pytest.raises(RuntimeError, match="business.password"):
        load_database_config(path)


@pytest.mark.parametrize("port", [0, 65536, "3306", True])
def test_rejects_invalid_port(tmp_path, port):
    path = tmp_path / "database_config.json"
    data = valid_config()
    data["business"]["port"] = port
    write_config(path, data)

    with pytest.raises(RuntimeError, match="business.port"):
        load_database_config(path)


@pytest.mark.parametrize("database", ["", "bad-name", "bad name"])
def test_rejects_invalid_database_name(tmp_path, database):
    path = tmp_path / "database_config.json"
    data = valid_config()
    data["auth"]["database"] = database
    write_config(path, data)

    with pytest.raises(RuntimeError, match="auth.database"):
        load_database_config(path)
