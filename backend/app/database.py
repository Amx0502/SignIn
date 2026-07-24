import re
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .database_config import ConnectionSettings
from .db_models import Base


_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
DatabaseSettings = ConnectionSettings


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
