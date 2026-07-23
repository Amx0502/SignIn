# Database User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store login users and sessions in a separate MySQL `User` database and add an admin-only first-level user-management page.

**Architecture:** Add an independent authentication database engine, relational user/session models, and a transactional repository. Refactor authentication to query this repository, expose admin and password-change APIs, then add role-aware Vue routes, menu items, and management dialogs.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, PyMySQL, PBKDF2-HMAC-SHA256, pytest, Vue 3, Element Plus

## Global Constraints

- Authentication data uses MySQL database `User`; check-in data remains in `xxqd`.
- Authentication settings use `AUTH_DB_HOST`, `AUTH_DB_PORT`, `AUTH_DB_NAME`, `AUTH_DB_USER`, and `AUTH_DB_PASSWORD`.
- `users` has no email column and API responses contain no email.
- Runtime authentication never reads or writes `users.json` or `sessions.json`.
- Only administrators may call user-management APIs or see the first-level user-management menu.
- The system must retain at least one active administrator.
- New and reset-password users must change their password before using business APIs.
- Tests use uniquely named temporary databases and never modify production `User`.

---

## File Structure

- Create `backend/app/auth_models.py`: authentication ORM models.
- Create `backend/app/auth_database.py`: independent authentication database settings and lifecycle.
- Create `backend/app/auth_repository.py`: password hashing, migration, sessions, user CRUD, and invariants.
- Rewrite `backend/app/auth.py`: authentication orchestration backed by `AuthRepository`.
- Modify `backend/app/models.py`: user-management and password-change request models.
- Modify `backend/app/main.py`: dual-database lifespan, authentication dependencies, and APIs.
- Create `backend/tests/test_auth_repository.py`: authentication repository and migration tests.
- Create `backend/tests/test_user_api.py`: authentication, authorization, and user API tests.
- Create `frontend/src/views/UserManagement.vue`: administrator user table and dialogs.
- Create `frontend/src/views/ChangePassword.vue`: mandatory password-change page.
- Modify `frontend/src/api/index.js`: authentication and user API functions.
- Modify `frontend/src/router/index.js`: role and password-change route guards.
- Modify `frontend/src/App.vue`: first-level admin menu.
- Modify `README.md`: authentication database configuration and initial administrator.

### Task 1: Authentication Database and Models

**Files:**
- Create: `backend/app/auth_database.py`
- Create: `backend/app/auth_models.py`
- Create: `backend/tests/test_auth_repository.py`

**Interfaces:**
- Produces: `AuthDatabaseSettings.from_env() -> AuthDatabaseSettings`
- Produces: `AuthDatabase.initialize()`, `session()`, and `dispose()`
- Produces: `UserRow` and `UserSessionRow`

- [ ] **Step 1: Write the failing schema test**

```python
def test_auth_database_creates_only_auth_tables(auth_database):
    assert set(inspect(auth_database.engine).get_table_names()) == {
        "users", "user_sessions"
    }
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
cd backend
$env:AUTH_DB_PASSWORD="123456"
python -m pytest tests/test_auth_repository.py::test_auth_database_creates_only_auth_tables -v
```

Expected: FAIL because `app.auth_database` does not exist.

- [ ] **Step 3: Implement settings, bootstrap, and models**

Use independent defaults and require a password:

```python
@classmethod
def from_env(cls):
    return cls(
        host=os.getenv("AUTH_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("AUTH_DB_PORT", "3306")),
        name=os.getenv("AUTH_DB_NAME", "User"),
        user=os.getenv("AUTH_DB_USER", "root"),
        password=os.environ["AUTH_DB_PASSWORD"],
    )
```

Define `UserRow` with username, password hash, role, active and must-change flags, and timestamps. Define `UserSessionRow` with a cascading `user_id`, unique 64-character token hash, IP address, and timestamps.

- [ ] **Step 4: Run the schema test and verify GREEN**

Run:

```powershell
python -m pytest tests/test_auth_repository.py::test_auth_database_creates_only_auth_tables -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/auth_database.py backend/app/auth_models.py backend/tests/test_auth_repository.py
git commit -m "feat: add authentication database schema"
```

### Task 2: Passwords, Migration, and User Repository

**Files:**
- Create: `backend/app/auth_repository.py`
- Modify: `backend/tests/test_auth_repository.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`
- Produces: `verify_password(password: str, encoded: str) -> tuple[bool, bool]`
- Produces: `AuthRepository.initialize_users(path: Path) -> int`
- Produces: `list_users`, `create_user`, `update_user`, `reset_password`, and `delete_user`

- [ ] **Step 1: Write failing password and migration tests**

```python
def test_pbkdf2_password_round_trip():
    encoded = hash_password("secret123")
    assert verify_password("secret123", encoded) == (True, False)
    assert verify_password("wrong", encoded) == (False, False)

def test_empty_database_imports_users_without_email(repository, legacy_users_file):
    assert repository.initialize_users(legacy_users_file) == 1
    assert repository.list_users()[0].keys() == {
        "id", "username", "role", "is_active", "must_change_password",
        "created_at", "updated_at", "last_login"
    }
```

Add cases for default `admin/admin123`, idempotency, malformed-file rollback, duplicate usernames, and old SHA-256 hash upgrade.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_auth_repository.py -k "password or initialize or user" -v
```

Expected: FAIL because repository functions do not exist.

- [ ] **Step 3: Implement PBKDF2 and transactional user CRUD**

Encode passwords as:

```text
pbkdf2_sha256$600000$<hex-salt>$<hex-digest>
```

Use `hashlib.pbkdf2_hmac`, `secrets.token_bytes`, and `hmac.compare_digest`. Preserve compatibility with `<sha256>:<salt>` legacy hashes and return the second tuple value as `True` when an upgrade is required.

Enforce:

- unique usernames;
- role in `admin/user`;
- no self-delete;
- no delete, disable, or downgrade of the last active administrator;
- reset passwords with `must_change_password=true`.

- [ ] **Step 4: Run repository tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_auth_repository.py -v
```

Expected: all repository tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/auth_repository.py backend/tests/test_auth_repository.py
git commit -m "feat: add database user repository"
```

### Task 3: Database Authentication and Sessions

**Files:**
- Rewrite: `backend/app/auth.py`
- Modify: `backend/tests/test_auth_repository.py`

**Interfaces:**
- Produces: `AuthService(repository: AuthRepository)`
- Preserves: `login`, `logout`, and `verify_token`
- Produces: `change_password(user_id, current_password, new_password, current_token)`

- [ ] **Step 1: Write failing authentication tests**

Test successful login, uniform invalid-credential errors, disabled users, legacy hash upgrade, remember-me expiration, hashed session storage, logout, expiration, and forced password change.

```python
ok, result = service.login(LoginRequest(
    username="admin", password="admin123", remember_me=False
), "127.0.0.1")
assert ok is True
assert result["user"]["role"] == "admin"
assert "email" not in result["user"]
assert repository.has_raw_token(result["access_token"]) is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_auth_repository.py -k "login or session or logout or change_password" -v
```

Expected: FAIL because `AuthService` still uses JSON files.

- [ ] **Step 3: Rewrite AuthService**

Keep only in-memory login-attempt throttling. Delegate user lookup, password verification/upgrade, session creation, Token verification, logout, and password change to `AuthRepository`. Return user dictionaries without email.

- [ ] **Step 4: Run authentication tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_auth_repository.py -v
```

Expected: PASS and source scan finds no runtime JSON writes in `auth.py`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/auth.py backend/tests/test_auth_repository.py
git commit -m "refactor: authenticate with MySQL sessions"
```

### Task 4: FastAPI Authorization and User APIs

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_user_api.py`

**Interfaces:**
- Produces: `get_current_user()` and `require_admin()`
- Produces: `/api/auth/change-password` and `/api/users` endpoints

- [ ] **Step 1: Write failing API tests**

Test login, verify, change-password gating, administrator CRUD, ordinary-user 403 responses, duplicate username 400 responses, session invalidation, and last-admin protection.

```python
response = client.get("/api/users", headers=user_headers)
assert response.status_code == 403

response = client.get("/api/users", headers=admin_headers)
assert response.status_code == 200
assert "email" not in response.text
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```powershell
python -m pytest tests/test_user_api.py -v
```

Expected: FAIL because user-management routes do not exist.

- [ ] **Step 3: Add dual-database lifecycle and APIs**

Initialize `AuthDatabase` in lifespan, run the one-time user migration, construct `AuthRepository` and `AuthService`, and dispose both databases on shutdown.

Add request models:

- `UserCreate`
- `UserUpdate`
- `PasswordReset`
- `PasswordChange`

Use database user IDs in user-management URLs. Apply `require_admin` to every `/api/users` endpoint and forced-password-change enforcement to business dependencies.

- [ ] **Step 4: Run all backend tests**

Run:

```powershell
python -m pytest tests -v
```

Expected: all existing and new tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models.py backend/app/main.py backend/tests/test_user_api.py
git commit -m "feat: add user management APIs"
```

### Task 5: Vue User Management and Password Change

**Files:**
- Create: `frontend/src/views/UserManagement.vue`
- Create: `frontend/src/views/ChangePassword.vue`
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`

**Interfaces:**
- Consumes: `/api/users` and `/api/auth/change-password`
- Produces: `/users` and `/change-password` routes

- [ ] **Step 1: Add API functions and pages**

Add:

```javascript
export const getUsersApi = () => instance.get('/users')
export const createUserApi = data => instance.post('/users', data)
export const updateUserApi = (id, data) => instance.put(`/users/${id}`, data)
export const resetUserPasswordApi = (id, data) => instance.post(`/users/${id}/reset-password`, data)
export const deleteUserApi = id => instance.delete(`/users/${id}`)
export const changePasswordApi = data => instance.post('/auth/change-password', data)
```

Build an Element Plus table with create/edit/reset/delete dialogs and no email field. Build a password-change form requiring current password, new password, and confirmation.

- [ ] **Step 2: Add role-aware routes and first-level menu**

Add route meta:

```javascript
{ path: '/users', meta: { requiresAuth: true, requiresAdmin: true } }
{ path: '/change-password', meta: { requiresAuth: true, allowPasswordChange: true } }
```

Read the stored user role and `must_change_password` in the router guard. Add a top-level `el-menu-item` for `/users` outside the existing check-in submenu and render it only for administrators.

- [ ] **Step 3: Build the frontend**

Run:

```powershell
cd frontend
npm.cmd run build
```

Expected: Vite exits 0.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/views/UserManagement.vue frontend/src/views/ChangePassword.vue frontend/src/api/index.js frontend/src/router/index.js frontend/src/App.vue
git commit -m "feat: add admin user management interface"
```

### Task 6: Production Migration, Documentation, and Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Verifies: production `User` schema, migration, tests, source scans, and frontend build

- [ ] **Step 1: Document authentication database settings**

Document:

```powershell
$env:AUTH_DB_HOST="127.0.0.1"
$env:AUTH_DB_PORT="3306"
$env:AUTH_DB_NAME="User"
$env:AUTH_DB_USER="root"
$env:AUTH_DB_PASSWORD="<数据库密码>"
```

Document the initial administrator, forced password change, and one-time migration.

- [ ] **Step 2: Initialize production authentication database**

Run initialization with both database passwords set. Verify `User` contains exactly `users` and `user_sessions`, then report the migrated/default user count without printing hashes.

- [ ] **Step 3: Run final backend verification**

Run:

```powershell
cd backend
python -m pytest tests -q -p no:cacheprovider --basetemp .codex-test-tmp
rg -n "USER_DATA_FILE|SESSION_DATA_FILE|_save_users|_save_sessions" app
```

Expected: all tests PASS and no runtime JSON authentication symbols remain.

- [ ] **Step 4: Run final frontend verification**

Run:

```powershell
cd ../frontend
npm.cmd run build
```

Expected: Vite exits 0.

- [ ] **Step 5: Review and commit**

Run:

```powershell
cd ..
git diff --check
git status --short
```

Then:

```powershell
git add README.md
git commit -m "docs: document authentication database"
```
