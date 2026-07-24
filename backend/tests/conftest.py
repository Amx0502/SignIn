import uuid

import pytest
from sqlalchemy import create_engine, text

from app.database import DatabaseSettings
from app.database_config import load_database_config


@pytest.fixture
def mysql_settings():
    local_settings = load_database_config().business
    database_name = f"xxqd_test_{uuid.uuid4().hex}"
    settings = DatabaseSettings(
        host=local_settings.host,
        port=local_settings.port,
        name=database_name,
        user=local_settings.user,
        password=local_settings.password,
    )
    yield settings

    server_engine = create_engine(settings.server_url(), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{database_name}`"))
    finally:
        server_engine.dispose()
