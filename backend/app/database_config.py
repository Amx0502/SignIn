import re
from dataclasses import dataclass

from sqlalchemy import URL

from . import config

UNIFIED_DATABASE_NAME = "SignIn"
_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


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


def _required_value(variable: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"数据库环境变量 {variable} 未配置")
    return value


def load_database_config() -> ConnectionSettings:
    host = _required_value("DATABASE_HOST", config.DATABASE_HOST)
    database = _required_value("DATABASE_NAME", config.DATABASE_NAME)
    user = _required_value("DATABASE_USER", config.DATABASE_USER)
    password = _required_value("DATABASE_PASSWORD", config.DATABASE_PASSWORD)
    try:
        port = int(_required_value("DATABASE_PORT", config.DATABASE_PORT))
    except ValueError as exc:
        raise RuntimeError("数据库环境变量 DATABASE_PORT 必须是整数") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(
            "数据库环境变量 DATABASE_PORT 必须是 1 到 65535 的整数"
        )

    if not _DATABASE_NAME_PATTERN.fullmatch(database):
        raise RuntimeError(
            "数据库环境变量 DATABASE_NAME 只能包含字母、数字和下划线"
        )

    if database != UNIFIED_DATABASE_NAME:
        raise RuntimeError(
            f"数据库环境变量 DATABASE_NAME 必须为 {UNIFIED_DATABASE_NAME}"
        )

    return ConnectionSettings(
        host=host,
        port=port,
        name=database,
        user=user,
        password=password,
    )
