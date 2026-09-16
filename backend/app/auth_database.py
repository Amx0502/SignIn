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
            if "expires_at" not in columns:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN expires_at DATETIME NULL")
                )
            if "platform_scope" not in columns:
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN platform_scope "
                    "VARCHAR(16) NOT NULL DEFAULT 'all'"
                ))
            card_definitions = {
                "card_type": "VARCHAR(16) NULL",
                "card_activated_at": "DATETIME NULL",
                "card_used_at": "DATETIME NULL",
                "card_total_uses": "INT NOT NULL DEFAULT 1",
                "card_used_count": "INT NOT NULL DEFAULT 0",
                "card_delete_delay_seconds": "INT NOT NULL DEFAULT 30",
                "card_delete_due_at": "DATETIME NULL",
            }
            added_card_columns: set[str] = set()
            for name, definition in card_definitions.items():
                if name not in columns:
                    added_card_columns.add(name)
                    connection.execute(text(
                        f"ALTER TABLE users ADD COLUMN {name} {definition}"
                    ))
            if (
                "card_delete_delay_seconds" in added_card_columns
                and "card_delete_delay_minutes" in columns
            ):
                connection.execute(text(
                    "UPDATE users SET card_delete_delay_seconds = "
                    "GREATEST(COALESCE(card_delete_delay_minutes, 0) * 60, 0) "
                    "WHERE card_type IS NOT NULL"
                ))
            if "card_delete_delay_minutes" in columns:
                connection.execute(text(
                    "ALTER TABLE users DROP COLUMN card_delete_delay_minutes"
                ))
            policy_columns = {
                column["name"]
                for column in inspect(connection).get_columns(
                    "user_feature_policies"
                )
            }
            policy_definitions = {
                "xxqd_account_limit": "INT NULL",
                "location_search_daily_limit": "INT NULL",
                "location_search_used": "INT NOT NULL DEFAULT 0",
                "location_search_date": "DATE NULL",
            }
            for name, definition in policy_definitions.items():
                if name not in policy_columns:
                    connection.execute(text(
                        "ALTER TABLE user_feature_policies "
                        f"ADD COLUMN {name} {definition}"
                    ))
            if "class_cube_only" in policy_columns:
                connection.execute(text(
                    "UPDATE users AS users "
                    "JOIN user_feature_policies AS policies "
                    "ON policies.user_id = users.id "
                    "SET users.platform_scope = 'class_cube' "
                    "WHERE users.role = 'user' "
                    "AND users.platform_scope = 'all' "
                    "AND policies.class_cube_only = 1"
                ))
                connection.execute(text(
                    "ALTER TABLE user_feature_policies "
                    "DROP COLUMN class_cube_only"
                ))

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
