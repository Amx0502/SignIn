from sqlalchemy import Connection, Engine, inspect, text

from .membership_constants import DEFAULT_CARD_DELETE_DELAY_SECONDS
from .schema_migrations import SchemaMigration, SchemaMigrationManager


def _columns(connection: Connection, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in inspect(connection).get_columns(table_name)
    }


def _apply_membership_baseline(connection: Connection) -> None:
    user_columns = _columns(connection, "users")
    if "must_change_password" in user_columns:
        connection.execute(text(
            "ALTER TABLE users DROP COLUMN must_change_password"
        ))
    if "expires_at" not in user_columns:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN expires_at DATETIME NULL"
        ))
    if "platform_scope" not in user_columns:
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
        "card_delete_delay_seconds": (
            "INT NOT NULL DEFAULT "
            f"{DEFAULT_CARD_DELETE_DELAY_SECONDS}"
        ),
        "card_delete_due_at": "DATETIME NULL",
        "initial_password_enc": "BLOB NULL",
    }
    added_card_columns: set[str] = set()
    for name, definition in card_definitions.items():
        if name not in user_columns:
            added_card_columns.add(name)
            connection.execute(text(
                f"ALTER TABLE users ADD COLUMN {name} {definition}"
            ))

    if (
        "card_delete_delay_seconds" in added_card_columns
        and "card_delete_delay_minutes" in user_columns
    ):
        connection.execute(text(
            "UPDATE users SET card_delete_delay_seconds = "
            "GREATEST(COALESCE(card_delete_delay_minutes, 0) * 60, 0) "
            "WHERE card_type IS NOT NULL"
        ))
    if "card_delete_delay_minutes" in user_columns:
        connection.execute(text(
            "ALTER TABLE users DROP COLUMN card_delete_delay_minutes"
        ))

    policy_columns = _columns(connection, "user_feature_policies")
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


def _synchronize_monthly_cleanup_schedule(connection: Connection) -> None:
    connection.execute(text(
        "UPDATE users "
        "SET card_delete_due_at = expires_at "
        "WHERE card_type = 'monthly' "
        "AND expires_at IS NOT NULL "
        "AND card_delete_due_at IS NULL"
    ))


def _add_initial_password_enc(connection: Connection) -> None:
    user_columns = _columns(connection, "users")
    if "initial_password_enc" not in user_columns:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN initial_password_enc BLOB NULL"
        ))


def _add_user_remark(connection: Connection) -> None:
    user_columns = _columns(connection, "users")
    if "remark" not in user_columns:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN remark VARCHAR(255) NULL"
        ))


def _add_user_created_by(connection: Connection) -> None:
    user_columns = _columns(connection, "users")
    if "created_by" not in user_columns:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN created_by VARCHAR(50) NULL"
        ))


def _add_user_archive_indexes(connection: Connection) -> None:
    indexes = {
        index["name"]
        for index in inspect(connection).get_indexes("users")
    }
    if "ix_users_expires_at" not in indexes:
        connection.execute(text(
            "CREATE INDEX ix_users_expires_at ON users (expires_at)"
        ))
    if "ix_users_card_cleanup_due" not in indexes:
        connection.execute(text(
            "CREATE INDEX ix_users_card_cleanup_due "
            "ON users (card_type, card_delete_due_at)"
        ))


AUTH_MIGRATIONS = (
    SchemaMigration(
        version=1,
        name="membership_and_platform_baseline",
        upgrade=_apply_membership_baseline,
    ),
    SchemaMigration(
        version=2,
        name="synchronize_monthly_cleanup_schedule",
        upgrade=_synchronize_monthly_cleanup_schedule,
    ),
    SchemaMigration(
        version=3,
        name="add_user_archive_indexes",
        upgrade=_add_user_archive_indexes,
    ),
    SchemaMigration(
        version=4,
        name="add_initial_password_enc",
        upgrade=_add_initial_password_enc,
    ),
    SchemaMigration(
        version=5,
        name="add_user_remark",
        upgrade=_add_user_remark,
    ),
    SchemaMigration(
        version=6,
        name="add_user_created_by",
        upgrade=_add_user_created_by,
    ),
)


def migrate_auth_schema(engine: Engine) -> list[int]:
    return SchemaMigrationManager(engine).apply(AUTH_MIGRATIONS)
