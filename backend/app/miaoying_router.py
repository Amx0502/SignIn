from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from .miaoying_client import MiaoyingRemoteError
from .miaoying_models import MiaoyingAccountUpdate, MiaoyingTaskPayload
from .miaoying_service import MiaoyingNotFound, MiaoyingValidationError


def create_miaoying_router(auth_dependency, menu_dependency=None):
    router = APIRouter(prefix="/api/miaoying", tags=["miaoying"])
    guard = lambda key: menu_dependency(key) if menu_dependency else auth_dependency

    def invoke(request, operation, *args):
        try: return {"ok": True, "data": operation(*args)}
        except MiaoyingNotFound as exc: return JSONResponse(status_code=404, content={"ok":False,"error":str(exc)})
        except MiaoyingValidationError as exc: return JSONResponse(status_code=400, content={"ok":False,"error":str(exc)})
        except MiaoyingRemoteError as exc: return JSONResponse(status_code=502, content={"ok":False,"error":str(exc),"retryable":True})
        except Exception:
            return JSONResponse(status_code=500, content={"ok":False,"error":"秒应服务内部错误"})

    @router.post("/qr-sessions")
    def create_qr(request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.create_qr, user)
    @router.get("/qr-sessions/{session_id}")
    def poll_qr(session_id: str, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.poll_qr, session_id, user)
    @router.get("/accounts")
    def accounts(request: Request, user=Depends(guard(("miaoying.overview","miaoying.accounts","miaoying.auto","miaoying.tasks")))): return invoke(request, request.app.state.miaoying_service.list_accounts, user)
    @router.put("/accounts/{account_id}")
    def update_account(account_id: int, payload: MiaoyingAccountUpdate, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.update_account, account_id, payload.model_dump(), user)
    @router.delete("/accounts/{account_id}")
    def delete_account(account_id: int, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.delete_account, account_id, user)
    @router.post("/accounts/{account_id}/forms/sync")
    def sync_forms(account_id: int, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.sync_forms, account_id, user)
    @router.get("/accounts/{account_id}/forms")
    def forms(account_id: int, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto","miaoying.tasks")))): return invoke(request, request.app.state.miaoying_service.list_forms, account_id, user)
    @router.get("/tasks")
    def tasks(request: Request, user=Depends(guard(("miaoying.overview","miaoying.auto","miaoying.tasks")))): return invoke(request, request.app.state.miaoying_service.list_tasks, user)
    @router.post("/tasks")
    def create_task(payload: MiaoyingTaskPayload, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.create_task, payload.model_dump(), user)
    @router.put("/tasks/{task_id}")
    def update_task(task_id: int, payload: MiaoyingTaskPayload, request: Request, user=Depends(guard(("miaoying.auto","miaoying.tasks")))): return invoke(request, request.app.state.miaoying_service.update_task, task_id, payload.model_dump(), user)
    @router.delete("/tasks/{task_id}")
    def delete_task(task_id: int, request: Request, user=Depends(guard("miaoying.tasks"))): return invoke(request, request.app.state.miaoying_service.delete_task, task_id, user)
    @router.post("/tasks/{task_id}/run")
    def run_task(task_id: int, request: Request, user=Depends(guard(("miaoying.auto","miaoying.tasks")))): return invoke(request, request.app.state.miaoying_service.run_task, task_id, user)
    @router.get("/runs")
    def runs(request: Request, limit: int=Query(100,ge=1,le=500), user=Depends(guard(("miaoying.runs","miaoying.logs","miaoying.overview")))): return invoke(request, request.app.state.miaoying_service.list_runs, user, limit)
    return router
