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
                self._migrate_task_table(database_engine)
                self._migrate_task_run_table(database_engine)
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

    @staticmethod
    def _migrate_task_table(engine: Engine) -> None:
        table = "class_cube_tasks"
        columns = {
            column["name"]
            for column in inspect(engine).get_columns(table)
        }
        definitions = {
            "schedule_times_json": "TEXT NOT NULL",
            "start_date": "DATE NULL",
            "end_date": "DATE NULL",
            "notify_wecom": "TINYINT(1) NOT NULL DEFAULT 1",
            "last_schedule_key": "VARCHAR(32) NOT NULL DEFAULT ''",
        }
        statements = [
            f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
            for name, definition in definitions.items()
            if name not in columns
        ]
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if "schedule_times_json" not in columns:
                connection.execute(
                    text(
                        "UPDATE class_cube_tasks "
                        "SET schedule_times_json='[]' "
                        "WHERE schedule_times_json IS NULL"
                    )
                )

    @staticmethod
    def _migrate_task_run_table(engine: Engine) -> None:
        table = "class_cube_task_runs"
        inspector = inspect(engine)
        columns = {
            column["name"]: column
            for column in inspector.get_columns(table)
        }
        definitions = {
            "source": "VARCHAR(32) NOT NULL DEFAULT 'task'",
            "owner_user_id": "BIGINT NULL",
            "account_id": "BIGINT NULL",
            "course_id": "BIGINT NULL",
        }
        foreign_keys = inspector.get_foreign_keys(table)
        task_foreign_key = next(
            (
                foreign_key
                for foreign_key in foreign_keys
                if foreign_key.get("constrained_columns") == ["task_id"]
            ),
            None,
        )
        quote = engine.dialect.identifier_preparer.quote

        with engine.begin() as connection:
            for name, definition in definitions.items():
                if name not in columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN "
                            f"{name} {definition}"
                        )
                    )
            connection.execute(
                text(
                    "UPDATE class_cube_task_runs AS runs "
                    "JOIN class_cube_tasks AS tasks "
                    "ON tasks.id = runs.task_id "
                    "SET runs.owner_user_id = tasks.owner_user_id, "
                    "runs.account_id = tasks.account_id, "
                    "runs.course_id = tasks.course_id, "
                    "runs.source = 'task' "
                    "WHERE runs.owner_user_id IS NULL "
                    "OR runs.account_id IS NULL "
                    "OR runs.course_id IS NULL"
                )
            )
            missing_scope = connection.execute(
                text(
                    "SELECT COUNT(*) FROM class_cube_task_runs "
                    "WHERE owner_user_id IS NULL "
                    "OR account_id IS NULL OR course_id IS NULL"
                )
            ).scalar_one()
            if missing_scope:
                raise RuntimeError(
                    "班级魔方运行记录作用域字段回填失败"
                )
            for name in ("owner_user_id", "account_id", "course_id"):
                column = columns.get(name)
                if column is None or column.get("nullable", True):
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} MODIFY COLUMN "
                            f"{name} BIGINT NOT NULL"
                        )
                    )

            task_id = columns.get("task_id", {})
            if task_id and not task_id.get("nullable", False):
                constraint_name = (
                    task_foreign_key or {}
                ).get("name")
                if constraint_name:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} DROP FOREIGN KEY "
                            f"{quote(constraint_name)}"
                        )
                    )
                connection.execute(
                    text(
                        f"ALTER TABLE {table} "
                        "MODIFY COLUMN task_id BIGINT NULL"
                    )
                )
                if constraint_name:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} ADD CONSTRAINT "
                            f"{quote(constraint_name)} FOREIGN KEY "
                            "(task_id) REFERENCES class_cube_tasks(id) "
                            "ON DELETE CASCADE"
                        )
                    )

        checkin_item = columns.get("checkin_item_id", {})
        if checkin_item and not checkin_item.get("nullable", False):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE class_cube_task_runs "
                        "MODIFY COLUMN checkin_item_id BIGINT NULL"
                    )
                )

        existing_indexes = {
            index["name"]
            for index in inspect(engine).get_indexes(table)
        }
        index_columns = {
            "ix_class_cube_task_runs_source": "source",
            "ix_class_cube_task_runs_owner_user_id": "owner_user_id",
            "ix_class_cube_task_runs_account_id": "account_id",
            "ix_class_cube_task_runs_course_id": "course_id",
        }
        with engine.begin() as connection:
            for index_name, column_name in index_columns.items():
                if index_name not in existing_indexes:
                    connection.execute(
                        text(
                            f"CREATE INDEX {quote(index_name)} "
                            f"ON {table} ({column_name})"
                        )
                    )

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
