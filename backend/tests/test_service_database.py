import pytest

from app.database import Database
from app.repository import AccountRepository
from app.service import AppState


@pytest.fixture
def database(mysql_settings):
    database = Database(mysql_settings)
    database.initialize()
    try:
        yield database
    finally:
        database.dispose()


def test_app_state_persists_crud_across_instances(database):
    first = AppState(repository=AccountRepository(database), start_scheduler=False)
    first.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret", "token": ""}
    )
    first.add_task(0, {"index": 1, "title": "task", "times": ["08:00:00"]})
    first.update_account(
        0, {"name": "B", "mobile": "13800000000", "password": "new", "token": ""}
    )
    first.shutdown()

    second = AppState(repository=AccountRepository(database), start_scheduler=False)
    try:
        snapshot = second.snapshot()
        assert snapshot["account_count"] == 1
        assert snapshot["accounts"][0]["name"] == "B"
        assert snapshot["accounts"][0]["tasks"][0]["title"] == "task"

        second.delete_task(0, 0)
        second.delete_account(0)
        assert second.snapshot()["accounts"] == []
    finally:
        second.shutdown()


def test_run_all_reads_tasks_added_after_state_construction(database):
    repository = AccountRepository(database)
    state = AppState(repository=repository, start_scheduler=False)
    queued = []
    state.enqueue_task = lambda account, task: queued.append((account, task))
    repository.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret", "token": ""}
    )
    repository.add_task(0, {"index": 1, "title": "late", "enable": True})

    try:
        assert state.run_all_enabled_tasks() == {"queued_count": 1}
        assert queued[0][1]["title"] == "late"
    finally:
        state.shutdown()
