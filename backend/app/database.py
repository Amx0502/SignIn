import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import Engine, URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .db_models import Base


_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        try:
            password = os.environ["DB_PASSWORD"]
        except KeyError as exc:
            raise RuntimeError("缺少数据库密码环境变量 DB_PASSWORD") from exc
        return cls(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            name=os.getenv("DB_NAME", "xxqd"),
            user=os.getenv("DB_USER", "root"),
            password=password,
        )

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


class Database:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("数据库尚未初始化")
        return self._engine

    def initialize(self) -> None:
        if not _DATABASE_NAME_PATTERN.fullmatch(self.settings.name):
            raise ValueError("数据库名称只能包含字母、数字和下划线")

        server_engine = create_engine(
            self.settings.server_url(),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with server_engine.connect() as connection:
                connection.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{self.settings.name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
        finally:
            server_engine.dispose()

        self._engine = create_engine(self.settings.url(), pool_pre_ping=True)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._session_factory is None:
            raise RuntimeError("数据库尚未初始化")
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None
