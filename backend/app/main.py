import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .models import AccountCreate, AccountUpdate, ApiResponse, Settings, TaskCreate, TaskUpdate
from .service import AppState

app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    app_state.shutdown()


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


@app.get("/api/state")
def get_state():
    return success(app_state.snapshot())


@app.get("/api/logs")
def get_logs(limit: int = 200):
    return success(app_state.get_logs(limit))


@app.post("/api/accounts")
def add_account(payload: AccountCreate):
    return success(app_state.add_account(payload.model_dump()))


@app.put("/api/accounts/{account_index}")
def update_account(account_index: int, payload: AccountUpdate):
    try:
        return success(app_state.update_account(account_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.delete("/api/accounts/{account_index}")
def delete_account(account_index: int):
    try:
        app_state.delete_account(account_index)
        return success(True)
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/login")
def login_account(account_index: int):
    try:
        return success(app_state.login_account(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/refresh-token")
def refresh_token(account_index: int):
    try:
        return success(app_state.refresh_single_token(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.get("/api/accounts/{account_index}/projects")
def fetch_projects(account_index: int):
    try:
        return success(app_state.fetch_projects(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/{account_index}/tasks")
def add_task(account_index: int, payload: TaskCreate):
    try:
        return success(app_state.add_task(account_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.put("/api/accounts/{account_index}/tasks/{task_index}")
def update_task(account_index: int, task_index: int, payload: TaskUpdate):
    try:
        return success(app_state.update_task(account_index, task_index, payload.model_dump()))
    except IndexError:
        failure("索引越界，请重新选择账号或任务")


@app.delete("/api/accounts/{account_index}/tasks/{task_index}")
def delete_task(account_index: int, task_index: int):
    try:
        app_state.delete_task(account_index, task_index)
        return success(True)
    except IndexError:
        failure("索引越界，请重新选择账号或任务")


@app.post("/api/accounts/{account_index}/tasks/{task_index}/run")
def run_task(account_index: int, task_index: int):
    try:
        return success(app_state.run_task(account_index, task_index))
    except IndexError:
        failure("索引越界，请重新选择账号或任务")


@app.post("/api/accounts/{account_index}/run-all")
def run_account_tasks(account_index: int):
    try:
        return success(app_state.run_account_tasks(account_index))
    except IndexError:
        failure("索引越界，请重新选择账号")


@app.post("/api/accounts/refresh-all")
def refresh_all_tokens():
    return success(app_state.refresh_all_tokens())


@app.post("/api/run-all")
def run_all_enabled_tasks():
    return success(app_state.run_all_enabled_tasks())


@app.post("/api/settings")
def set_settings(payload: Settings):
    return success(app_state.set_settings(payload.model_dump()))


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "image.jpg").suffix
    name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    target = config.UPLOAD_DIR / name
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
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
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=True)
