import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from sqlalchemy import UniqueConstraint

from app.class_cube_database import ClassCubeDatabase
from app.class_cube_db_models import ClassCubeBase
from app.database_config import ConnectionSettings, load_database_config


class ClassCubeConfigTest(unittest.TestCase):
    @staticmethod
    def connection(database: str) -> dict[str, object]:
        return {
            "host": "127.0.0.1",
            "port": 3306,
            "database": database,
            "user": "root",
            "password": "secret",
        }

    def test_loads_class_cube_database_section(self):
        payload = {
            "business": self.connection("xxqd"),
            "auth": self.connection("User"),
            "class_cube": self.connection("bjmf"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database_config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_database_config(path)
        self.assertEqual(config.class_cube.name, "bjmf")

    def test_requires_class_cube_database_section(self):
        payload = {
            "business": self.connection("xxqd"),
            "auth": self.connection("User"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database_config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "class_cube"):
                load_database_config(path)

    def test_requires_bjmf_as_class_cube_database_name(self):
        payload = {
            "business": self.connection("xxqd"),
            "auth": self.connection("User"),
            "class_cube": self.connection("another_database"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database_config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "bjmf"):
                load_database_config(path)


class ClassCubeModelTest(unittest.TestCase):
    EXPECTED_COLUMNS = {
        "class_cube_accounts": {
            "id",
            "owner_user_id",
            "name",
            "remote_user_name",
            "cookie",
            "status",
            "last_login_at",
            "created_at",
            "updated_at",
        },
        "class_cube_courses": {
            "id",
            "account_id",
            "remote_course_id",
            "name",
            "class_code",
            "payload",
            "synced_at",
            "created_at",
            "updated_at",
        },
        "class_cube_checkin_items": {
            "id",
            "course_id",
            "remote_item_id",
            "title",
            "mode",
            "remote_module",
            "form_action",
            "form_schema",
            "status",
            "start_at",
            "end_at",
            "synced_at",
            "created_at",
            "updated_at",
        },
        "class_cube_tasks": {
            "id",
            "owner_user_id",
            "account_id",
            "course_id",
            "name",
            "enabled",
            "poll_interval_seconds",
            "latitude",
            "longitude",
            "accuracy",
            "photo_path",
            "password",
            "last_scan_at",
            "created_at",
            "updated_at",
        },
        "class_cube_task_runs": {
            "id",
            "task_id",
            "checkin_item_id",
            "remote_item_id",
            "mode",
            "status",
            "message",
            "response_summary",
            "started_at",
            "finished_at",
        },
        "class_cube_task_item_claims": {
            "id",
            "task_id",
            "checkin_item_id",
            "remote_item_id",
            "state",
            "last_run_id",
            "created_at",
            "updated_at",
        },
    }

    def test_declares_all_class_cube_tables(self):
        self.assertEqual(
            set(ClassCubeBase.metadata.tables),
            {
                "class_cube_accounts",
                "class_cube_courses",
                "class_cube_checkin_items",
                "class_cube_tasks",
                "class_cube_task_runs",
                "class_cube_task_item_claims",
            },
        )

    def test_declares_all_required_columns(self):
        actual = {
            name: set(table.columns.keys())
            for name, table in ClassCubeBase.metadata.tables.items()
        }
        self.assertEqual(actual, self.EXPECTED_COLUMNS)

    def test_declares_only_required_unique_constraints(self):
        expected = {
            "class_cube_accounts": set(),
            "class_cube_courses": {("account_id", "remote_course_id")},
            "class_cube_checkin_items": {
                ("course_id", "remote_item_id", "remote_module")
            },
            "class_cube_tasks": set(),
            "class_cube_task_runs": set(),
            "class_cube_task_item_claims": {("task_id", "remote_item_id")},
        }
        actual = {}
        for name, table in ClassCubeBase.metadata.tables.items():
            actual[name] = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
        self.assertEqual(actual, expected)

    def test_uses_cascading_parent_foreign_keys(self):
        expected = {
            ("class_cube_courses", "account_id"),
            ("class_cube_checkin_items", "course_id"),
            ("class_cube_tasks", "account_id"),
            ("class_cube_tasks", "course_id"),
            ("class_cube_task_runs", "task_id"),
            ("class_cube_task_runs", "checkin_item_id"),
            ("class_cube_task_item_claims", "task_id"),
            ("class_cube_task_item_claims", "checkin_item_id"),
        }
        actual = {
            (table.name, foreign_key.parent.name)
            for table in ClassCubeBase.metadata.tables.values()
            for foreign_key in table.foreign_keys
            if foreign_key.ondelete == "CASCADE"
        }
        self.assertEqual(actual, expected)

    def test_task_poll_interval_defaults_to_thirty_seconds(self):
        column = ClassCubeBase.metadata.tables[
            "class_cube_tasks"
        ].columns.poll_interval_seconds
        self.assertIsNotNone(column.default)
        self.assertEqual(column.default.arg, 30)


class ClassCubeDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.settings = ConnectionSettings(
            host="127.0.0.1",
            port=3306,
            name="bjmf",
            user="root",
            password="secret",
        )

    @patch("app.class_cube_database.ClassCubeBase.metadata.create_all")
    @patch("app.class_cube_database.sessionmaker")
    @patch("app.class_cube_database.create_engine")
    def test_initializes_database_and_tables(
        self, create_engine, sessionmaker, create_all
    ):
        server_engine = MagicMock()
        database_engine = MagicMock()
        create_engine.side_effect = [server_engine, database_engine]

        database = ClassCubeDatabase(self.settings)
        database.initialize()

        self.assertEqual(
            create_engine.call_args_list,
            [
                call(
                    self.settings.server_url(),
                    isolation_level="AUTOCOMMIT",
                    pool_pre_ping=True,
                ),
                call(self.settings.url(), pool_pre_ping=True),
            ],
        )
        create_all.assert_called_once_with(database_engine)
        self.assertIs(database.engine, database_engine)
        sessionmaker.assert_called_once_with(
            bind=database_engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def test_session_commits_and_closes(self):
        database = ClassCubeDatabase(self.settings)
        session = MagicMock()
        database._session_factory = MagicMock(return_value=session)

        with database.session() as yielded:
            self.assertIs(yielded, session)

        session.commit.assert_called_once_with()
        session.rollback.assert_not_called()
        session.close.assert_called_once_with()

    def test_session_rolls_back_and_closes_on_error(self):
        database = ClassCubeDatabase(self.settings)
        session = MagicMock()
        database._session_factory = MagicMock(return_value=session)

        with self.assertRaisesRegex(ValueError, "boom"):
            with database.session():
                raise ValueError("boom")

        session.commit.assert_not_called()
        session.rollback.assert_called_once_with()
        session.close.assert_called_once_with()

    def test_dispose_releases_engine_and_resets_state(self):
        database = ClassCubeDatabase(self.settings)
        engine = MagicMock()
        database._engine = engine
        database._session_factory = MagicMock()

        database.dispose()

        engine.dispose.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "尚未初始化"):
            _ = database.engine
        with self.assertRaisesRegex(RuntimeError, "尚未初始化"):
            with database.session():
                pass

    @patch("app.class_cube_database.create_engine")
    def test_rejects_non_bjmf_database_name(self, create_engine):
        settings = ConnectionSettings(
            host="127.0.0.1",
            port=3306,
            name="another_database",
            user="root",
            password="secret",
        )

        with self.assertRaisesRegex(ValueError, "bjmf"):
            ClassCubeDatabase(settings).initialize()

        create_engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
