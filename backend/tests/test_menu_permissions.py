from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth_models import AuthBase, UserRow
from app.menu_catalog import build_effective_menu, visible_menu_keys
from app.menu_repository import MenuRepository, MenuVersionConflictError


class DatabaseHarness:
    def __init__(self, path):
        self.engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )
        self.sessions = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        AuthBase.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        session = self.sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


@pytest.fixture
def menu_repository(tmp_path):
    database = DatabaseHarness(tmp_path / "menus.sqlite3")
    with database.session() as session:
        session.add_all([
            UserRow(
                id=1,
                username="admin",
                password_hash="unused",
                role="admin",
                is_active=True,
            ),
            UserRow(
                id=2,
                username="member",
                password_hash="unused",
                role="user",
                is_active=True,
            ),
        ])
    repository = MenuRepository(database)
    repository.initialize()
    return repository


def test_child_visibility_is_independent_from_siblings(menu_repository):
    updated = menu_repository.update_global(
        expected_version=1,
        visibility={"xxqd.overview": False},
        actor_user_id=1,
    )

    catalog = menu_repository.effective_catalog({"id": 2, "role": "user"})
    keys = visible_menu_keys(catalog["menus"])

    assert updated["version"] == 2
    assert "xxqd" in keys
    assert "xxqd.overview" not in keys
    assert "xxqd.accounts" in keys


def test_hidden_parent_preserves_child_setting_for_later_restore(menu_repository):
    menu_repository.update_global(
        expected_version=1,
        visibility={"xxqd": False, "xxqd.overview": True},
        actor_user_id=1,
    )
    hidden = menu_repository.effective_catalog({"id": 2, "role": "user"})
    assert "xxqd" not in visible_menu_keys(hidden["menus"])

    menu_repository.update_global(
        expected_version=2,
        visibility={"xxqd": True},
        actor_user_id=1,
    )
    restored = menu_repository.effective_catalog({"id": 2, "role": "user"})
    assert "xxqd.overview" in visible_menu_keys(restored["menus"])


def test_user_override_supports_inherit_visible_and_hidden(menu_repository):
    menu_repository.update_global(
        expected_version=1,
        visibility={"class_cube.overview": False},
        actor_user_id=1,
    )
    menu_repository.update_user_overrides(
        expected_version=2,
        user_id=2,
        overrides={
            "class_cube.overview": "visible",
            "class_cube.tasks": "hidden",
        },
        actor_user_id=1,
    )

    keys = visible_menu_keys(
        menu_repository.effective_catalog({"id": 2, "role": "user"})["menus"]
    )
    assert "class_cube.overview" in keys
    assert "class_cube.tasks" not in keys

    menu_repository.update_user_overrides(
        expected_version=3,
        user_id=2,
        overrides={"class_cube.overview": "inherit"},
        actor_user_id=1,
    )
    inherited_keys = visible_menu_keys(
        menu_repository.effective_catalog({"id": 2, "role": "user"})["menus"]
    )
    assert "class_cube.overview" not in inherited_keys


def test_admin_always_receives_the_full_catalog(menu_repository):
    menu_repository.update_global(
        expected_version=1,
        visibility={"xxqd": False, "class_cube": False},
        actor_user_id=1,
    )
    keys = visible_menu_keys(
        menu_repository.effective_catalog({"id": 1, "role": "admin"})["menus"]
    )
    assert "xxqd" in keys
    assert "xxqd.overview" in keys
    assert "class_cube" in keys


def test_stale_admin_update_is_rejected(menu_repository):
    menu_repository.update_global(
        expected_version=1,
        visibility={"xxqd.overview": False},
        actor_user_id=1,
    )

    with pytest.raises(MenuVersionConflictError) as error:
        menu_repository.update_global(
            expected_version=1,
            visibility={"xxqd.accounts": False},
            actor_user_id=1,
        )

    assert error.value.current_version == 2


def test_two_admins_cannot_commit_the_same_version(menu_repository):
    def update(menu_key):
        try:
            result = menu_repository.update_global(
                expected_version=1,
                visibility={menu_key: False},
                actor_user_id=1,
            )
            return ("saved", result["version"])
        except MenuVersionConflictError as error:
            return ("conflict", error.current_version)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["xxqd.overview", "xxqd.accounts"]))

    assert sorted(status for status, _ in results) == ["conflict", "saved"]
    assert menu_repository.current_version() == 2


def test_failed_audit_write_rolls_back_configuration_and_version(
    menu_repository,
    monkeypatch,
):
    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(menu_repository, "_record_audit", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        menu_repository.update_global(
            expected_version=1,
            visibility={"xxqd.overview": False},
            actor_user_id=1,
        )

    assert menu_repository.current_version() == 1
    keys = visible_menu_keys(
        menu_repository.effective_catalog({"id": 2, "role": "user"})["menus"]
    )
    assert "xxqd.overview" in keys


def test_audit_log_contains_before_after_target_and_version(menu_repository):
    menu_repository.update_user_overrides(
        expected_version=1,
        user_id=2,
        overrides={"xxqd.overview": "hidden"},
        actor_user_id=1,
    )

    log = menu_repository.list_audit_logs(limit=10)[0]
    assert log["actor_user_id"] == 1
    assert log["target_type"] == "user"
    assert log["target_user_id"] == 2
    assert log["version"] == 2
    assert log["before"] == {"xxqd.overview": "inherit"}
    assert log["after"] == {"xxqd.overview": "hidden"}


def test_full_form_save_audits_only_changed_items_and_noop_keeps_version(
    menu_repository,
):
    result = menu_repository.update_global(
        expected_version=1,
        visibility={
            "xxqd": True,
            "xxqd.overview": False,
            "xxqd.accounts": True,
        },
        actor_user_id=1,
    )
    log = menu_repository.list_audit_logs(limit=10)[0]
    assert result["version"] == 2
    assert log["before"] == {"xxqd.overview": True}
    assert log["after"] == {"xxqd.overview": False}

    noop = menu_repository.update_global(
        expected_version=2,
        visibility={
            "xxqd": True,
            "xxqd.overview": False,
            "xxqd.accounts": True,
        },
        actor_user_id=1,
    )
    assert noop["version"] == 2
    assert len(menu_repository.list_audit_logs(limit=10)) == 1


def test_user_full_form_save_audits_only_changed_overrides(menu_repository):
    result = menu_repository.update_user_overrides(
        expected_version=1,
        user_id=2,
        overrides={
            "xxqd": "inherit",
            "xxqd.overview": "hidden",
            "xxqd.accounts": "inherit",
        },
        actor_user_id=1,
    )
    log = menu_repository.list_audit_logs(limit=10)[0]
    assert result["version"] == 2
    assert log["before"] == {"xxqd.overview": "inherit"}
    assert log["after"] == {"xxqd.overview": "hidden"}


def test_catalog_builder_suppresses_children_when_parent_is_hidden():
    menus = build_effective_menu(
        global_visibility={"xxqd": False, "xxqd.overview": True},
        overrides={},
        is_admin=False,
    )
    assert "xxqd" not in visible_menu_keys(menus)
