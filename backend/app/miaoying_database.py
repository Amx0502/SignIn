from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .database_config import ConnectionSettings, UNIFIED_DATABASE_NAME
from .miaoying_db_models import MiaoyingBase


class MiaoyingDatabase:
    def __init__(self, settings: ConnectionSettings):
        self.settings = settings
        self.engine = None
        self.factory = None

    def initialize(self) -> None:
        if self.settings.name != UNIFIED_DATABASE_NAME:
            raise RuntimeError(f"秒应数据库名称必须为 {UNIFIED_DATABASE_NAME}")
        self.engine = create_engine(self.settings.url(), pool_pre_ping=True)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        MiaoyingBase.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self.factory is None:
            raise RuntimeError("秒应数据库尚未初始化")
        session = self.factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
        self.engine = None
        self.factory = None
