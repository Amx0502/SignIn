import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.database import DatabaseSettings


@pytest.fixture
def mysql_settings():
    database_name = f"xxqd_test_{uuid.uuid4().hex}"
    settings = DatabaseSettings(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        name=database_name,
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "123456"),
    )
    yield settings

    server_engine = create_engine(settings.server_url(), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{database_name}`"))
    finally:
        server_engine.dispose()
