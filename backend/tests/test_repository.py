import pytest

from app.database import Database
from app.repository import AccountIndexError, AccountRepository, DuplicateMobileError


@pytest.fixture
def repository(mysql_settings):
    database = Database(mysql_settings)
    database.initialize()
    try:
        yield AccountRepository(database)
    finally:
        database.dispose()


@pytest.fixture
def seeded_account(repository):
    repository.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret", "token": ""}
    )
    return repository


def test_account_crud_uses_rows_and_preserves_response_shape(repository):
    created = repository.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret", "token": ""}
    )
    assert created == {
        "name": "A",
        "mobile": "13800000000",
        "password": "secret",
        "token": "",
        "tasks": [],
        "projects": [],
    }

    updated = repository.update_account(
        0,
        {"name": "B", "mobile": "13800000000", "password": "new", "token": "t"},
    )
    assert updated["name"] == "B"
    assert repository.list_accounts()[0]["token"] == "t"

    repository.delete_account(0)
    assert repository.list_accounts() == []


def test_duplicate_mobile_is_a_business_error(repository):
    data = {"name": "A", "mobile": "13800000000", "password": "secret"}
    repository.add_account(data)

    with pytest.raises(DuplicateMobileError):
        repository.add_account({**data, "name": "B"})


def test_invalid_account_indexes_are_rejected(repository):
    with pytest.raises(AccountIndexError):
        repository.update_account(
            0, {"name": "A", "mobile": "13800000000", "password": "secret"}
        )
    with pytest.raises(AccountIndexError):
        repository.delete_account(-1)


def test_tasks_are_crud_rows_with_contiguous_positions(seeded_account):
    repository = seeded_account
    repository.add_task(0, {"index": 1, "title": "one", "times": ["08:00:00"]})
    repository.add_task(0, {"index": 2, "title": "two", "times": ["09:00:00"]})
    updated = repository.update_task(
        0, 1, {"index": 3, "title": "updated", "times": ["10:00:00"]}
    )
    assert updated["title"] == "updated"

    repository.delete_task(0, 0)

    accounts = repository.list_accounts()
    assert [task["title"] for task in accounts[0]["tasks"]] == ["updated"]
    assert repository.task_positions(0) == [0]


def test_token_and_projects_update_only_target_account(repository):
    repository.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret"}
    )
    repository.add_account(
        {"name": "B", "mobile": "13900000000", "password": "secret"}
    )

    repository.update_token(0, "token-a")
    assert repository.update_token_by_mobile("13900000000", "token-b") is True
    assert repository.update_token_by_mobile("13700000000", "missing") is False
    projects = [{"id": 2, "name": "second"}, {"id": 1, "name": "first"}]
    assert repository.replace_projects(0, projects) == projects

    accounts = repository.list_accounts()
    assert [account["token"] for account in accounts] == ["token-a", "token-b"]
    assert accounts[0]["projects"] == projects
    assert accounts[1]["projects"] == []


def test_deleting_account_cascades_tasks_and_projects(seeded_account):
    repository = seeded_account
    repository.add_task(0, {"index": 1, "title": "one"})
    repository.replace_projects(0, [{"id": 1}])

    repository.delete_account(0)

    assert repository.child_counts() == {"tasks": 0, "projects": 0}
