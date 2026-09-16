from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, Engine, text


@dataclass(frozen=True)
class SchemaMigration:
    version: int
    name: str
    upgrade: Callable[[Connection], None]


class SchemaMigrationManager:
    def __init__(
        self,
        engine: Engine,
        *,
        table_name: str = "schema_migrations",
    ) -> None:
        self.engine = engine
        self.table_name = table_name

    def apply(self, migrations: Sequence[SchemaMigration]) -> list[int]:
        ordered = sorted(migrations, key=lambda migration: migration.version)
        versions = [migration.version for migration in ordered]
        if len(versions) != len(set(versions)):
            raise ValueError("迁移版本号不能重复")

        newly_applied: list[int] = []
        with self.engine.begin() as connection:
            connection.execute(text(
                f"CREATE TABLE IF NOT EXISTS {self.table_name} ("
                "version INT NOT NULL PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "applied_at DATETIME NOT NULL"
                ")"
            ))
            applied_versions = set(connection.scalars(text(
                f"SELECT version FROM {self.table_name}"
            )).all())
            for migration in ordered:
                if migration.version in applied_versions:
                    continue
                migration.upgrade(connection)
                connection.execute(
                    text(
                        f"INSERT INTO {self.table_name} "
                        "(version, name, applied_at) "
                        "VALUES (:version, :name, :applied_at)"
                    ),
                    {
                        "version": migration.version,
                        "name": migration.name,
                        "applied_at": datetime.now(),
                    },
                )
                newly_applied.append(migration.version)
        return newly_applied
