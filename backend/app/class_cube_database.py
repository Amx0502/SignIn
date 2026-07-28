from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.pool import NullPool
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
            poolclass=NullPool,
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

        database_engine = create_engine(
            self.settings.url(),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            pool_recycle=1800,
        )
        try:
            ClassCubeBase.metadata.create_all(database_engine)
            if database_engine.dialect.name == "mysql":
                self._migrate_claim_table(database_engine)
            session_factory = sessionmaker(
                bind=database_engine,
                autoflush=False,
                expire_on_commit=False,
            )
        except Exception:
            database_engine.dispose()
            raise

        self._engine = database_engine
        self._session_factory = session_factory

    @staticmethod
    def _migrate_claim_table(engine: Engine) -> None:
        table = "class_cube_task_item_claims"
        inspector = inspect(engine)
        columns = {
            column["name"] for column in inspector.get_columns(table)
        }
        unique_constraints = {
            constraint.get("name"): tuple(
                constraint.get("column_names") or ()
            )
            for constraint in inspector.get_unique_constraints(table)
        }
        statements = []
        if "remote_module" not in columns:
            statements.append(
                "ALTER TABLE class_cube_task_item_claims "
                "ADD COLUMN remote_module VARCHAR(32) NOT NULL "
                "DEFAULT 'punchs' AFTER remote_item_id"
            )
        if "lease_until" not in columns:
            statements.append(
                "ALTER TABLE class_cube_task_item_claims "
                "ADD COLUMN lease_until DATETIME NULL AFTER last_run_id"
            )
        if "lease_token" not in columns:
            statements.append(
                "ALTER TABLE class_cube_task_item_claims "
                "ADD COLUMN lease_token VARCHAR(64) NOT NULL "
                "DEFAULT '' AFTER lease_until"
            )
        if "phase" not in columns:
            statements.append(
                "ALTER TABLE class_cube_task_item_claims "
                "ADD COLUMN phase VARCHAR(32) NOT NULL "
                "DEFAULT 'submitting' AFTER lease_token"
            )
        existing = unique_constraints.get(
            "uq_class_cube_claims_task_remote"
        )
        required = ("task_id", "remote_module", "remote_item_id")
        if existing != required:
            if existing:
                statements.append(
                    "ALTER TABLE class_cube_task_item_claims "
                    "DROP INDEX uq_class_cube_claims_task_remote"
                )
            statements.append(
                "ALTER TABLE class_cube_task_item_claims ADD UNIQUE KEY "
                "uq_class_cube_claims_task_remote "
                "(task_id, remote_module, remote_item_id)"
            )
        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))

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
