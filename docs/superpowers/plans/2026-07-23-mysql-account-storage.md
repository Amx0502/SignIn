# MySQL Account Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace runtime CRUD against `backend/accounts.json` with transactional MySQL 5.7 CRUD while preserving the existing API and frontend behavior.

**Architecture:** Add a SQLAlchemy database bootstrap layer, relational ORM models, and an `AccountRepository` that converts relational rows to the existing nested account dictionaries. Refactor `AppState` to query the repository for every snapshot, mutation, Token update, project refresh, and scheduler cycle; retain JSON only as an idempotent one-time import source.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, PyMySQL, MySQL 5.7.44, pytest

## Global Constraints

- Production database is MySQL 5.7.44 at `127.0.0.1:3306`, database `xxqd`, user `root`.
- Read connection settings from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.
- Never log or commit database passwords or account passwords.
- Keep all existing frontend API paths and response shapes unchanged.
- Do not migrate `settings.json`, `users.json`, or `sessions.json`.
- Never fall back to runtime reads or writes of `accounts.json`.
- MySQL integration tests must only delete a uniquely generated temporary database.

---

## File Structure

- Create `backend/app/database.py`: environment configuration, server connection, database creation, engine/session lifecycle, and schema initialization.
- Create `backend/app/db_models.py`: SQLAlchemy declarations for accounts, tasks, and account projects.
- Create `backend/app/repository.py`: transactional CRUD, list-index resolution, relational-to-dictionary conversion, and one-time JSON import.
- Modify `backend/app/config.py`: remove runtime `DATA_FILE`; retain an explicitly named legacy import path.
- Modify `backend/app/service.py`: replace `self.accounts` and disk-save operations with repository calls.
- Modify `backend/app/main.py`: initialize the database in FastAPI lifespan and map repository errors to current API errors.
- Modify `backend/requirements.txt`: add SQLAlchemy, PyMySQL, and pytest.
- Modify `.gitignore`: ignore local `.env` and generated database-test artifacts without ignoring source fixtures.
- Modify `README.md`: document MySQL setup and environment variables.
- Create `backend/tests/conftest.py`: temporary MySQL database fixture and application fixtures.
- Create `backend/tests/test_database.py`: bootstrap and MySQL-version behavior.
- Create `backend/tests/test_repository.py`: repository CRUD and migration behavior.
- Create `backend/tests/test_service_database.py`: `AppState` database integration and scheduling freshness.
- Create `backend/tests/test_api_compatibility.py`: existing HTTP contract compatibility.

### Task 1: Database Bootstrap and Relational Schema

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/db_models.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_database.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `DatabaseSettings.from_env() -> DatabaseSettings`
- Produces: `Database(settings: DatabaseSettings)` with `initialize()`, `session()`, and `dispose()`
- Produces: ORM classes `AccountRow`, `TaskRow`, and `AccountProjectRow`

- [ ] **Step 1: Add test dependencies and write the failing bootstrap test**

Add these dependencies:

```text
SQLAlchemy>=2.0.30,<2.1
PyMySQL>=1.1.0,<2
pytest>=8.2.0,<9
```

Create a fixture that generates `xxqd_test_<uuid>` and removes only that exact database in teardown. The bootstrap assertion is:

```python
def test_initialize_creates_database_and_tables(mysql_settings):
    database = Database(mysql_settings)
    database.initialize()

    with database.engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())

    assert table_names == {"accounts", "tasks", "account_projects"}
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
cd backend
python -m pytest tests/test_database.py::test_initialize_creates_database_and_tables -v
```

Expected: FAIL because `app.database` does not exist.

- [ ] **Step 3: Implement database settings and bootstrap**

Implement immutable settings and URL construction without interpolating an unescaped password:

```python
@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        return cls(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            name=os.getenv("DB_NAME", "xxqd"),
            user=os.getenv("DB_USER", "root"),
            password=os.environ["DB_PASSWORD"],
        )

    def url(self, database: str | None = None) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database if database is not None else self.name,
            query={"charset": "utf8mb4"},
        )
```

`Database.initialize()` must validate the database identifier using `^[A-Za-z0-9_]+$`, execute `CREATE DATABASE IF NOT EXISTS \`name\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`, create the target engine with `pool_pre_ping=True`, and call `Base.metadata.create_all(engine)`.

Define:

```python
class AccountRow(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
```

Define `TaskRow` and `AccountProjectRow` with `ForeignKey("accounts.id", ondelete="CASCADE")`; use `UniqueConstraint("account_id", "position")`, MySQL `JSON` columns for arrays/payloads, and relationships with `cascade="all, delete-orphan"` and `order_by="position"`.

- [ ] **Step 4: Run the bootstrap test**

Run:

```powershell
python -m pytest tests/test_database.py -v
```

Expected: PASS; teardown reports no attempt to drop `xxqd`.

- [ ] **Step 5: Commit the database foundation**

```powershell
git add backend/app/database.py backend/app/db_models.py backend/tests/conftest.py backend/tests/test_database.py backend/requirements.txt
git commit -m "feat: add MySQL database foundation"
```

### Task 2: Account Repository CRUD

**Files:**
- Create: `backend/app/repository.py`
- Create: `backend/tests/test_repository.py`

**Interfaces:**
- Consumes: `Database.session()`
- Produces: `AccountRepository.list_accounts() -> list[dict]`
- Produces: `add_account(data: dict) -> dict`, `update_account(index: int, data: dict) -> dict`, and `delete_account(index: int) -> None`
- Produces: `AccountIndexError(IndexError)`, `TaskIndexError(IndexError)`, and `DuplicateMobileError(ValueError)`

- [ ] **Step 1: Write failing account CRUD tests**

Test a complete red-green sequence:

```python
def test_account_crud_uses_rows_and_preserves_response_shape(repository):
    created = repository.add_account(
        {"name": "A", "mobile": "13800000000", "password": "secret", "token": ""}
    )
    assert created == {
        "name": "A", "mobile": "13800000000", "password": "secret",
        "token": "", "tasks": [], "projects": [],
    }

    updated = repository.update_account(
        0, {"name": "B", "mobile": "13800000000", "password": "new", "token": "t"}
    )
    assert updated["name"] == "B"
    assert repository.list_accounts()[0]["token"] == "t"

    repository.delete_account(0)
    assert repository.list_accounts() == []
```

Also assert duplicate mobile raises `DuplicateMobileError` and invalid indexes raise `AccountIndexError`.

- [ ] **Step 2: Verify repository tests fail**

Run:

```powershell
python -m pytest tests/test_repository.py -v
```

Expected: FAIL because `AccountRepository` does not exist.

- [ ] **Step 3: Implement account row conversion and transactions**

Implement stable ordering and eager loading:

```python
def list_accounts(self) -> list[dict]:
    with self.database.session() as session:
        rows = session.scalars(
            select(AccountRow)
            .options(selectinload(AccountRow.tasks), selectinload(AccountRow.projects))
            .order_by(AccountRow.id)
        ).all()
        return [self._account_to_dict(row) for row in rows]

def _resolve_account(self, session: Session, index: int) -> AccountRow:
    if index < 0:
        raise AccountIndexError(index)
    row = session.scalar(select(AccountRow).order_by(AccountRow.id).offset(index).limit(1))
    if row is None:
        raise AccountIndexError(index)
    return row
```

Each write must use `with self.database.session() as session:` and commit through the session context manager. Convert only MySQL duplicate-key errors for the `mobile` unique index to `DuplicateMobileError`; re-raise other database errors.

- [ ] **Step 4: Run repository CRUD tests**

Run:

```powershell
python -m pytest tests/test_repository.py -v
```

Expected: all account CRUD and error tests PASS.

- [ ] **Step 5: Commit account repository CRUD**

```powershell
git add backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: add transactional account repository"
```

### Task 3: Task, Token, and Project Repository Operations

**Files:**
- Modify: `backend/app/repository.py`
- Modify: `backend/tests/test_repository.py`

**Interfaces:**
- Produces: `add_task(account_index: int, data: dict) -> dict`
- Produces: `update_task(account_index: int, task_index: int, data: dict) -> dict`
- Produces: `delete_task(account_index: int, task_index: int) -> None`
- Produces: `update_token(account_index: int, token: str) -> dict`
- Produces: `update_token_by_mobile(mobile: str, token: str) -> bool`
- Produces: `replace_projects(account_index: int, projects: list[dict]) -> list[dict]`

- [ ] **Step 1: Write failing nested-data tests**

```python
def test_tasks_are_crud_rows_with_contiguous_positions(repository, seeded_account):
    repository.add_task(0, {"index": 1, "title": "one", "times": ["08:00:00"]})
    repository.add_task(0, {"index": 2, "title": "two", "times": ["09:00:00"]})
    repository.delete_task(0, 0)

    accounts = repository.list_accounts()
    assert [task["title"] for task in accounts[0]["tasks"]] == ["two"]
    assert repository.task_positions(0) == [0]
```

Add tests for Token update, project replacement order, and account deletion cascading to both child tables.

- [ ] **Step 2: Verify nested-data tests fail**

Run:

```powershell
python -m pytest tests/test_repository.py -k "tasks or token or projects or cascade" -v
```

Expected: FAIL because nested repository methods do not exist.

- [ ] **Step 3: Implement nested transactional operations**

Resolve account and task indexes with stable ordering. Store `times` and `pic_path` as JSON arrays. On delete, lock remaining task rows and assign positions in list order:

```python
remaining = session.scalars(
    select(TaskRow)
    .where(TaskRow.account_id == account.id)
    .order_by(TaskRow.position, TaskRow.id)
    .with_for_update()
).all()
for position, row in enumerate(remaining):
    row.position = position
```

Replace projects by clearing `account.projects`, flushing, then appending `AccountProjectRow(position=i, payload=project)` for every project in the same transaction.

- [ ] **Step 4: Run the full repository suite**

Run:

```powershell
python -m pytest tests/test_repository.py -v
```

Expected: PASS with account, task, Token, project, and cascade cases.

- [ ] **Step 5: Commit nested repository operations**

```powershell
git add backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: persist tasks tokens and projects in MySQL"
```

### Task 4: Idempotent Legacy JSON Import

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/repository.py`
- Modify: `backend/tests/test_repository.py`

**Interfaces:**
- Produces: `LEGACY_ACCOUNTS_FILE`
- Produces: `AccountRepository.import_legacy_json_if_empty(path: Path) -> int`

- [ ] **Step 1: Write failing import tests**

Use a temporary JSON file containing one account with two tasks and one `projects` entry. Assert:

```python
assert repository.import_legacy_json_if_empty(path) == 1
assert repository.import_legacy_json_if_empty(path) == 0
assert len(repository.list_accounts()) == 1
assert len(repository.list_accounts()[0]["tasks"]) == 2
assert path.exists()
```

Add a malformed-file test asserting the transaction leaves all three tables empty.

- [ ] **Step 2: Verify import tests fail**

Run:

```powershell
python -m pytest tests/test_repository.py -k legacy -v
```

Expected: FAIL because the legacy import method does not exist.

- [ ] **Step 3: Implement empty-database import**

Rename `DATA_FILE` to:

```python
LEGACY_ACCOUNTS_FILE = APP_DIR / "accounts.json"
```

Within one transaction, return `0` immediately when `select(func.count(AccountRow.id))` is nonzero. Otherwise parse a top-level list, normalize each account and task, insert all relational rows, and return the number of imported accounts. Do not rename, delete, or write the source file.

- [ ] **Step 4: Run import and repository tests**

Run:

```powershell
python -m pytest tests/test_repository.py -v
```

Expected: PASS, including rollback and idempotency.

- [ ] **Step 5: Commit the importer**

```powershell
git add backend/app/config.py backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: import legacy accounts JSON once"
```

### Task 5: Refactor AppState to Use the Repository

**Files:**
- Modify: `backend/app/service.py`
- Create: `backend/tests/test_service_database.py`

**Interfaces:**
- Consumes: all `AccountRepository` methods from Tasks 2-4
- Produces: `AppState(repository: AccountRepository | None = None, start_scheduler: bool = True)`
- Preserves: all public `AppState` method signatures used by `main.py`

- [ ] **Step 1: Write failing AppState database tests**

Instantiate with a real temporary-database repository and `start_scheduler=False`. Assert that `add_account`, `update_account`, `delete_account`, task CRUD, and `snapshot()` persist across two separate `AppState` instances.

```python
first = AppState(repository=repository, start_scheduler=False)
first.add_account(account_data)
first.shutdown()

second = AppState(repository=AccountRepository(database), start_scheduler=False)
assert second.snapshot()["account_count"] == 1
```

- [ ] **Step 2: Verify AppState tests fail**

Run:

```powershell
python -m pytest tests/test_service_database.py -v
```

Expected: FAIL because `AppState` does not accept repository injection and still loads JSON.

- [ ] **Step 3: Replace cached-account and disk-save paths**

Remove `load_accounts_from_disk`, `save_accounts_to_disk`, and `self.accounts`. Keep normalization helpers. Use:

```python
self.repository = repository or AccountRepository(get_database())
```

Implement `snapshot()` from `accounts = self.repository.list_accounts()`. Delegate CRUD directly. After remote login call `repository.update_token`; after project fetch call `repository.replace_projects`. Batch Token refresh must update each successful account independently by stable index or mobile without overwriting other rows.

- [ ] **Step 4: Refactor scheduler reads and verify freshness**

At the start of `process_schedule()` and `run_all_enabled_tasks()`, call `repository.list_accounts()`. Add a test that inserts a task after constructing `AppState`, then asserts the next schedule evaluation sees it without restart.

- [ ] **Step 5: Run service tests**

Run:

```powershell
python -m pytest tests/test_service_database.py -v
```

Expected: PASS; source inspection finds no runtime JSON account save.

- [ ] **Step 6: Commit AppState refactor**

```powershell
git add backend/app/service.py backend/tests/test_service_database.py
git commit -m "refactor: use MySQL repository in application state"
```

### Task 6: Application Lifecycle and API Compatibility

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_compatibility.py`

**Interfaces:**
- Consumes: `Database.initialize()`, `Database.dispose()`, repository exceptions
- Preserves: `/api/state`, `/api/accounts`, and nested task endpoint contracts

- [ ] **Step 1: Write failing lifecycle and API tests**

Override authentication in the test app and assert create, update, state read, task create, task delete, and account delete responses retain `{"ok": True, "data": ...}`. Assert duplicate mobile returns HTTP 400 without SQL text.

- [ ] **Step 2: Verify API tests fail**

Run:

```powershell
python -m pytest tests/test_api_compatibility.py -v
```

Expected: FAIL because application lifecycle does not initialize the database and repository exceptions are not mapped.

- [ ] **Step 3: Initialize and dispose database in lifespan**

Use:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    app_state.repository.import_legacy_json_if_empty(config.LEGACY_ACCOUNTS_FILE)
    try:
        yield
    finally:
        app_state.shutdown()
        database.dispose()
```

Avoid constructing an `AppState` that starts its scheduler before database initialization; create application state during lifespan or initialize database before constructing it.

- [ ] **Step 4: Map repository errors**

Convert `DuplicateMobileError` to the existing HTTP 400 business envelope and `AccountIndexError`/`TaskIndexError` to the current index-out-of-range messages. Never include the original SQL exception string in client responses.

- [ ] **Step 5: Run API and backend tests**

Run:

```powershell
python -m pytest tests/test_api_compatibility.py -v
python -m pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit lifecycle and compatibility changes**

```powershell
git add backend/app/main.py backend/tests/test_api_compatibility.py
git commit -m "feat: initialize MySQL storage in app lifecycle"
```

### Task 7: Configuration Documentation and Final Verification

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Documents: production startup and environment configuration
- Verifies: backend tests, Python import, frontend build, and absence of account JSON runtime writes

- [ ] **Step 1: Update configuration documentation**

Document:

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_NAME="xxqd"
$env:DB_USER="root"
$env:DB_PASSWORD="<your-password>"
python run.py
```

State that the MySQL user needs permission to create `xxqd` when it is absent, and that an existing `backend/accounts.json` is imported only when `accounts` is empty. Keep `.env` ignored.

- [ ] **Step 2: Install dependencies and run the full backend test suite**

Run:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest tests -v
```

Expected: all tests PASS with zero failures.

- [ ] **Step 3: Verify backend imports and database initialization**

Run:

```powershell
python -c "from app.main import app; print(app.title)"
```

Expected: exit code 0 and the application title.

- [ ] **Step 4: Verify no runtime account JSON persistence remains**

Run:

```powershell
rg -n "save_accounts_to_disk|load_accounts_from_disk|DATA_FILE\\.write|DATA_FILE\\.open" backend/app
```

Expected: no matches. References to `LEGACY_ACCOUNTS_FILE` are allowed only in startup import code.

- [ ] **Step 5: Build the existing frontend**

Run:

```powershell
cd ../frontend
npm run build
```

Expected: Vite build exits 0.

- [ ] **Step 6: Review the complete diff against the design**

Run:

```powershell
cd ..
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only planned source, tests, dependency, ignore, and documentation files are changed.

- [ ] **Step 7: Commit documentation and verification adjustments**

```powershell
git add .gitignore README.md backend/requirements.txt
git commit -m "docs: document MySQL account storage"
```
