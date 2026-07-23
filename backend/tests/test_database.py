from sqlalchemy import inspect

from app.database import Database


def test_initialize_creates_database_and_tables(mysql_settings):
    database = Database(mysql_settings)
    database.initialize()

    try:
        with database.engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
        assert table_names == {"accounts", "tasks", "account_projects"}
    finally:
        database.dispose()
