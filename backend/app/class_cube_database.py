from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .class_cube_db_models import ClassCubeBase
from .database_config import ConnectionSettings


class ClassCubeDatabase:
    def __init__(self, settings: ConnectionSettings):
        self.settings = settings
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("班级魔方数据库尚未初始化")
        return self._engine

    def initialize(self) -> None:
        if self.settings.name != "bjmf":
            raise ValueError("班级魔方数据库名称必须为 bjmf")

        server_engine = create_engine(
            self.settings.server_url(),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with server_engine.connect() as connection:
                connection.execute(
                    text(
                        "CREATE DATABASE IF NOT EXISTS `bjmf` "
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
        ClassCubeBase.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._session_factory is None:
            raise RuntimeError("班级魔方数据库尚未初始化")
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
