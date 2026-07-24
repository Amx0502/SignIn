import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import URL


DATABASE_CONFIG_FILE = Path(__file__).resolve().parent.parent / "database_config.json"
_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_REQUIRED_FIELDS = ("host", "port", "database", "user", "password")


@dataclass(frozen=True)
class ConnectionSettings:
    host: str
    port: int
    name: str
    user: str
    password: str

    def url(self, database: str | None = None) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database if database is not None else self.name,
            query={"charset": "utf8mb4"},
        )

    def server_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            query={"charset": "utf8mb4"},
        )


@dataclass(frozen=True)
class DatabaseConfig:
    business: ConnectionSettings
    auth: ConnectionSettings


def _connection_settings(data: object, section: str, path: Path) -> ConnectionSettings:
    if not isinstance(data, dict):
        raise RuntimeError(f"数据库配置文件 {path} 中的 {section} 必须是对象")

    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise RuntimeError(f"数据库配置文件 {path} 缺少字段 {section}.{field}")

    port = data["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeError(
            f"数据库配置文件 {path} 的 {section}.port 必须是 1 到 65535 的整数"
        )

    for field in ("host", "database", "user", "password"):
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(
                f"数据库配置文件 {path} 的 {section}.{field} 必须是非空字符串"
            )

    database = data["database"]
    if not _DATABASE_NAME_PATTERN.fullmatch(database):
        raise RuntimeError(
            f"数据库配置文件 {path} 的 {section}.database "
            "只能包含字母、数字和下划线"
        )

    return ConnectionSettings(
        host=data["host"].strip(),
        port=port,
        name=database,
        user=data["user"].strip(),
        password=data["password"],
    )


def load_database_config(
    path: str | Path = DATABASE_CONFIG_FILE,
) -> DatabaseConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise RuntimeError(f"数据库配置文件不存在: {config_path}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"数据库配置文件 {config_path} JSON 格式错误: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"无法读取数据库配置文件 {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"数据库配置文件 {config_path} 的根节点必须是对象")

    for section in ("business", "auth"):
        if section not in data:
            raise RuntimeError(f"数据库配置文件 {config_path} 缺少配置段 {section}")

    return DatabaseConfig(
        business=_connection_settings(data["business"], "business", config_path),
        auth=_connection_settings(data["auth"], "auth", config_path),
    )
