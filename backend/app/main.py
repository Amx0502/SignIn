import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from . import config
from .auth import AuthService
from .auth_database import AuthDatabase
from .auth_repository import (
    AuthRepository,
    DuplicateUsernameError,
    LastAdminError,
    UserNotFoundError,
)
from .models import (
    AccountCreate,
    AccountUpdate,
    LoginRequest,
    PasswordChange,
    PasswordReset,
    Settings,
    TaskCreate,
    TaskUpdate,
    UserCreate,
    UserUpdate,
)
from .database_config import load_database_config
from .class_cube_client import ClassCubeClient
from .class_cube_database import ClassCubeDatabase
from .class_cube_repository import ClassCubeRepository
from .class_cube_router import create_class_cube_router
from .class_cube_service import ClassCubeService
from .class_cube_scheduler import ClassCubeScheduler
from .class_cube_logging import ClassCubeLogStore, create_class_cube_logger
from .menu_events import MenuEventBroker
from .menu_repository import MenuRepository
from .menu_router import create_menu_guard, create_menu_router
from .repository import DuplicateMobileError
from .service import AppState

app_state = AppState(start_scheduler=False)
auth_service = AuthService()
auth_database: AuthDatabase | None = None
class_cube_database: ClassCubeDatabase | None = None
menu_repository: MenuRepository | None = None
menu_event_broker = MenuEventBroker()
class_cube_log_store = ClassCubeLogStore()
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global auth_database, class_cube_database, menu_repository
    created_auth_repository = False
    class_cube_service: ClassCubeService | None = None
    class_cube_scheduler: ClassCubeScheduler | None = None
    try:
        database_config = load_database_config()
        app_state.initialize_database(database_config.business)
        app_state.repository.import_legacy_json_if_empty(
            config.LEGACY_ACCOUNTS_FILE
        )
        if auth_service.repository is None:
            auth_database = AuthDatabase(database_config.auth)
            auth_database.initialize()
            auth_repository = AuthRepository(auth_database)
            auth_repository.initialize_users(
                config.LEGACY_USERS_FILE
            )
            auth_service.set_repository(auth_repository)
            created_auth_repository = True

        menu_repository = MenuRepository(auth_service.repository.database)
        menu_repository.initialize()

        class_cube_database = ClassCubeDatabase(
            database_config.class_cube
        )
        class_cube_database.initialize()
        class_cube_logger = create_class_cube_logger(class_cube_log_store)
        app.state.class_cube_log_store = class_cube_log_store
        class_cube_service = ClassCubeService(
            ClassCubeRepository(class_cube_database),
            ClassCubeClient(),
            class_cube_logger,
        )
        app.state.class_cube_service = class_cube_service
        class_cube_scheduler = ClassCubeScheduler(class_cube_service)
        app.state.class_cube_scheduler = class_cube_scheduler
        app_state.start_background_scheduler()
        yield
    finally:
        try:
            if class_cube_scheduler is not None:
                class_cube_scheduler.shutdown()
            app.state.class_cube_scheduler = None
        finally:
            try:
                app_state.shutdown()
            finally:
                try:
                    if class_cube_service is not None:
                        class_cube_service.close()
                finally:
                    app.state.class_cube_service = None
                    try:
                        if class_cube_database is not None:
                            class_cube_database.dispose()
                    finally:
                        class_cube_database = None
                        if auth_database is not None:
                            auth_database.dispose()
                            auth_database = None
                        menu_repository = None
                        if created_auth_repository:
                            auth_service.repository = None


app = FastAPI(title="签到管理系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def success(data=None):
    return {"ok": True, "data": data}


def failure(message: str, status: int = 400):
    raise HTTPException(status_code=status, detail={"ok": False, "error": message})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "ok" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": str(exc.detail)})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    app_state.logger.error("请求处理失败: %s", exc)
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.exception_handler(DuplicateMobileError)
async def duplicate_mobile_exception_handler(
    request: Request, exc: DuplicateMobileError
):
    return JSONResponse(
        status_code=400,
        content={"ok": False, "error": str(exc)},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = auth_service.verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "error": "登录已过期，请重新登录"},
        )
    return user


async def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail={"ok": False, "error": "需要管理员权限"},
        )
    return user


def get_menu_repository() -> MenuRepository:
    if menu_repository is None:
        raise RuntimeError("菜单权限服务尚未初始化")
    return menu_repository


require_menu = create_menu_guard(get_current_user, get_menu_repository)
app.include_router(
    create_menu_router(
        get_current_user,
        require_admin,
        get_menu_repository,
        menu_event_broker,
    )
)
app.include_router(create_class_cube_router(get_current_user, require_menu))


@app.get("/api/state")
def get_state(_user=Depends(require_menu("xxqd"))):
    return success(app_state.snapshot())


@app.get("/api/xxqd/logs")
def get_logs(limit: int = 200, _user=Depends(require_menu("xxqd.logs"))):
    return success(app_state.get_logs(limit))


@app.post("/api/accounts")
def add_account(payload: AccountCreate, _user=Depends(require_menu("xxqd.accounts"))):
    return success(app_state.add_account(payload.model_dump()))


@app.put("/api/accounts/{account_index}")
def update_account(
    account_index: int,
    payload: AccountUpdate,
    _user=Depends(require_menu("xxqd.accounts")),
):
    try:
        return success(app_state.update_account(account_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.delete("/api/accounts/{account_index}")
def delete_account(account_index: int, _user=Depends(require_menu("xxqd.accounts"))):
    try:
        app_state.delete_account(account_index)
        return success(True)
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/login")
def login_account(account_index: int, _user=Depends(require_menu("xxqd.accounts"))):
    try:
        return success(app_state.login_account(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/refresh-token")
def refresh_token(account_index: int, _user=Depends(require_menu("xxqd.accounts"))):
    try:
        return success(app_state.refresh_single_token(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.get("/api/accounts/{account_index}/projects")
def fetch_projects(account_index: int, _user=Depends(require_menu("xxqd.accounts"))):
    try:
        return success(app_state.fetch_projects(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/tasks")
def add_task(
    account_index: int,
    payload: TaskCreate,
    _user=Depends(require_menu("xxqd.tasks")),
):
    try:
        return success(app_state.add_task(account_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.put("/api/accounts/{account_index}/tasks/{task_index}")
def update_task(
    account_index: int,
    task_index: int,
    payload: TaskUpdate,
    _user=Depends(require_menu("xxqd.tasks")),
):
    try:
        return success(app_state.update_task(account_index, task_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号或任务")


@app.delete("/api/accounts/{account_index}/tasks/{task_index}")
def delete_task(
    account_index: int,
    task_index: int,
    _user=Depends(require_menu("xxqd.tasks")),
):
    try:
        app_state.delete_task(account_index, task_index)
        return success(True)
    except IndexError:
        failure("索引越界，请重新选择账号或任务")


@app.post("/api/accounts/{account_index}/tasks/{task_index}/run")
def run_task(
    account_index: int,
    task_index: int,
    _user=Depends(require_menu("xxqd.tasks")),
):
    try:
        return success(app_state.run_task(account_index, task_index))
    except IndexError:
        failure("索引越界，请重新选择账号或任务")
    except RuntimeError as e:
        failure(str(e))


@app.post("/api/accounts/{account_index}/run-all")
def run_account_tasks(account_index: int, _user=Depends(require_menu("xxqd.auto"))):
    try:
        return success(app_state.run_account_tasks(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/refresh-all")
def refresh_all_tokens(_user=Depends(require_menu("xxqd.accounts"))):
    return success(app_state.refresh_all_tokens())


@app.post("/api/run-all")
def run_all_enabled_tasks(_user=Depends(require_menu("xxqd.auto"))):
    return success(app_state.run_all_enabled_tasks())


@app.post("/api/settings")
def set_settings(payload: Settings, _user=Depends(require_menu("xxqd.auto"))):
    return success(app_state.set_settings(payload.model_dump()))


@app.post("/api/auth/login")
def login(request: Request, payload: LoginRequest):
    ip_address = request.client.host if request.client else "unknown"
    ok, result = auth_service.login(payload, ip_address)
    if ok:
        return success(result)
    failure(result.get("error", "登录失败"), 401)


@app.post("/api/auth/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    auth_service.logout(token)
    return success(True)


@app.post("/api/auth/verify")
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user = auth_service.verify_token(token)
    if not user:
        failure("登录已过期，请重新登录", 401)
    return success(user)


@app.post("/api/auth/change-password")
def change_password(
    payload: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user=Depends(get_current_user),
):
    if not auth_service.change_password(
        user["id"],
        payload.current_password,
        payload.new_password,
        credentials.credentials,
    ):
        failure("当前密码错误")
    updated = auth_service.verify_token(credentials.credentials)
    return success(updated)


@app.get("/api/users")
def list_users(admin=Depends(require_admin)):
    return success(auth_service.repository.list_users())


@app.post("/api/users")
def create_user(payload: UserCreate, admin=Depends(require_admin)):
    try:
        return success(
            auth_service.repository.create_user(
                payload.username, payload.password, payload.role, payload.is_active
            )
        )
    except DuplicateUsernameError as exc:
        failure(str(exc))


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, admin=Depends(require_admin)):
    try:
        return success(
            auth_service.repository.update_user(
                user_id, payload.username, payload.role, payload.is_active
            )
        )
    except (DuplicateUsernameError, LastAdminError) as exc:
        failure(str(exc))
    except UserNotFoundError:
        failure("用户不存在", 404)


@app.post("/api/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    admin=Depends(require_admin),
):
    try:
        keep_hash = (
            auth_service.repository.token_hash(credentials.credentials)
            if user_id == admin["id"]
            else None
        )
        auth_service.repository.reset_password(user_id, payload.new_password, keep_hash)
        return success(True)
    except UserNotFoundError:
        failure("用户不存在", 404)


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin=Depends(require_admin)):
    try:
        auth_service.repository.delete_user(user_id, admin["id"])
        return success(True)
    except (LastAdminError, ValueError) as exc:
        failure(str(exc))
    except UserNotFoundError:
        failure("用户不存在", 404)





UPLOAD_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_MAX_SIZE = 10 * 1024 * 1024  # 10MB


@app.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    _user=Depends(require_menu("xxqd.tasks")),
):
    ext = Path(file.filename or "image.jpg").suffix.lower()
    if ext not in UPLOAD_ALLOWED_EXTENSIONS:
        failure("不支持的文件类型，仅允许 jpg/png/webp 格式")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    target = config.UPLOAD_DIR / name
    content_size = 0
    with target.open("wb") as buffer:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            content_size += len(chunk)
            if content_size > UPLOAD_MAX_SIZE:
                target.unlink(missing_ok=True)
                failure("文件过大，最大支持 10MB")
            buffer.write(chunk)
    return success({"path": str(target), "url": f"/uploads/{name}"})


config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    @app.get("/{full_path:path}")
    def spa_catch_all(full_path: str):
        target = FRONTEND_DIST / full_path
        if target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=True)
