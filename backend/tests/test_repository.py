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
