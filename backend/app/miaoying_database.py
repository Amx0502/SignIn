from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
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
        self._ensure_dynamic_form_columns()

    def _ensure_dynamic_form_columns(self) -> None:
        """Add columns introduced after the initial Miaoying schema."""
        with self.engine.begin() as connection:
            account_columns = {
                column["name"] for column in inspect(connection).get_columns("miaoying_accounts")
            }
            if "class_name" not in account_columns:
                connection.execute(
                    text(
                        "ALTER TABLE miaoying_accounts ADD COLUMN "
                        "class_name VARCHAR(128) NOT NULL DEFAULT ''"
                    )
                )

            task_columns = {
                column["name"] for column in inspect(connection).get_columns("miaoying_tasks")
            }
            if "answers" not in task_columns:
                if connection.dialect.name == "sqlite":
                    connection.execute(text("ALTER TABLE miaoying_tasks ADD COLUMN answers JSON NOT NULL DEFAULT '{}'"))
                else:
                    connection.execute(text("ALTER TABLE miaoying_tasks ADD COLUMN answers JSON NULL"))
                    connection.execute(text("UPDATE miaoying_tasks SET answers = '{}' WHERE answers IS NULL"))
                    if connection.dialect.name in {"mysql", "mariadb"}:
                        connection.execute(text("ALTER TABLE miaoying_tasks MODIFY COLUMN answers JSON NOT NULL"))
            if "answer_schema" not in task_columns:
                if connection.dialect.name == "sqlite":
                    connection.execute(text("ALTER TABLE miaoying_tasks ADD COLUMN answer_schema JSON NOT NULL DEFAULT '[]'"))
                else:
                    connection.execute(text("ALTER TABLE miaoying_tasks ADD COLUMN answer_schema JSON NULL"))
                    connection.execute(text("UPDATE miaoying_tasks SET answer_schema = '[]' WHERE answer_schema IS NULL"))
                    if connection.dialect.name in {"mysql", "mariadb"}:
                        connection.execute(text("ALTER TABLE miaoying_tasks MODIFY COLUMN answer_schema JSON NOT NULL"))

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
