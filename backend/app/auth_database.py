import re
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .auth_models import AuthBase
from .database_config import ConnectionSettings


_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
AuthDatabaseSettings = ConnectionSettings


class AuthDatabase:
    def __init__(self, settings: AuthDatabaseSettings):
        self.settings = settings
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("认证数据库尚未初始化")
        return self._engine

    def initialize(self) -> None:
        if not _NAME_PATTERN.fullmatch(self.settings.name):
            raise ValueError("认证数据库名称只能包含字母、数字和下划线")
        server = create_engine(self.settings.server_url(), isolation_level="AUTOCOMMIT")
        try:
            with server.connect() as connection:
                connection.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS `{self.settings.name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
        finally:
            server.dispose()
        self._engine = create_engine(self.settings.url(), pool_pre_ping=True)
        self._session_factory = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False
        )
        AuthBase.metadata.create_all(self._engine)
        with self._engine.begin() as connection:
            columns = {
                column["name"] for column in inspect(connection).get_columns("users")
            }
            if "must_change_password" in columns:
                connection.execute(
                    text("ALTER TABLE users DROP COLUMN must_change_password")
                )

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._session_factory is None:
            raise RuntimeError("认证数据库尚未初始化")
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
        if self._engine:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None

    def drop_database_for_test(self) -> None:
        if not self.settings.name.startswith("user_test_"):
            raise RuntimeError("拒绝删除非测试认证数据库")
        self.dispose()
        server = create_engine(self.settings.server_url(), isolation_level="AUTOCOMMIT")
        try:
            with server.connect() as connection:
                connection.execute(text(f"DROP DATABASE IF EXISTS `{self.settings.name}`"))
        finally:
            server.dispose()
