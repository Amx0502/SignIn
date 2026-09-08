import logging

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from .class_cube_models import (
    ClassCubeLocationReverseRequest,
    ClassCubeLocationSearchRequest,
)
from .class_cube_service import ClassCubeRemoteError, ClassCubeValidationError
from .miaoying_client import MiaoyingRemoteError
from .miaoying_models import (
    MiaoyingAccountUpdate,
    MiaoyingBatchDelete,
    MiaoyingBatchState,
    MiaoyingManualCheckin,
    MiaoyingSettingsUpdate,
    MiaoyingTaskPayload,
    MiaoyingWebhookTest,
)
from .miaoying_service import MiaoyingNotFound, MiaoyingValidationError


logger = logging.getLogger(__name__)


def create_miaoying_router(auth_dependency, menu_dependency=None):
    router = APIRouter(prefix="/api/miaoying", tags=["miaoying"])
    guard = lambda key: menu_dependency(key) if menu_dependency else auth_dependency

    def invoke(request, operation, *args):
        try: return {"ok": True, "data": operation(*args)}
        except MiaoyingNotFound as exc: return JSONResponse(status_code=404, content={"ok":False,"error":str(exc)})
        except MiaoyingValidationError as exc: return JSONResponse(status_code=400, content={"ok":False,"error":str(exc)})
        except ClassCubeValidationError as exc: return JSONResponse(status_code=400, content={"ok":False,"error":str(exc)})
        except ClassCubeRemoteError as exc: return JSONResponse(status_code=502, content={"ok":False,"error":exc.message,"retryable":exc.retryable})
        except MiaoyingRemoteError as exc: return JSONResponse(status_code=502, content={"ok":False,"error":str(exc),"retryable":exc.retryable})
        except Exception:
            logger.exception("秒应接口执行失败：%s", getattr(operation, "__name__", operation))
            return JSONResponse(status_code=500, content={"ok":False,"error":"秒应服务内部错误"})

    @router.post("/qr-sessions")
    def create_qr(request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.create_qr, user)
    @router.get("/qr-sessions/{session_id}")
    def poll_qr(session_id: str, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.poll_qr, session_id, user)
    @router.get("/accounts")
    def accounts(request: Request, user=Depends(guard(("miaoying.overview","miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.miaoying_service.list_accounts, user)
    @router.put("/accounts/{account_id}")
    def update_account(account_id: int, payload: MiaoyingAccountUpdate, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.update_account, account_id, payload.model_dump(), user)
    @router.delete("/accounts/{account_id}")
    def delete_account(account_id: int, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.delete_account, account_id, user)
    @router.post("/accounts/{account_id}/forms/sync")
    def sync_forms(account_id: int, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.miaoying_service.sync_forms, account_id, user)
    @router.post("/accounts/{account_id}/forms/sync-detailed")
    def sync_forms_detailed(account_id: int, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.miaoying_service.sync_forms_detailed, account_id, user)
    @router.get("/accounts/{account_id}/forms")
    def forms(account_id: int, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.miaoying_service.list_forms, account_id, user)
    @router.post("/accounts/{account_id}/images")
    async def upload_image(account_id: int, request: Request, file: UploadFile = File(...), user=Depends(guard(("miaoying.accounts","miaoying.auto")))):
        content = await file.read()
        return invoke(
            request,
            request.app.state.miaoying_service.upload_image,
            account_id,
            content,
            file.filename or "image.jpg",
            file.content_type or "application/octet-stream",
            user,
        )
    @router.post("/forms/{form_id}/checkin")
    def manual_checkin(form_id: int, payload: MiaoyingManualCheckin, request: Request, user=Depends(guard("miaoying.accounts"))): return invoke(request, request.app.state.miaoying_service.manual_checkin, form_id, payload.model_dump(), user)
    @router.get("/locations/config")
    def location_config(request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.class_cube_service.get_location_config, user)
    @router.post("/locations/search")
    def search_locations(payload: ClassCubeLocationSearchRequest, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.class_cube_service.search_locations, payload.query, payload.limit, payload.region, user)
    @router.post("/locations/reverse")
    def reverse_location(payload: ClassCubeLocationReverseRequest, request: Request, user=Depends(guard(("miaoying.accounts","miaoying.auto")))): return invoke(request, request.app.state.class_cube_service.reverse_location, payload.latitude, payload.longitude, user)
    @router.get("/settings")
    def get_settings(request: Request, user=Depends(guard("miaoying.overview"))): return invoke(request, request.app.state.miaoying_service.get_settings, user)
    @router.put("/settings")
    def update_settings(payload: MiaoyingSettingsUpdate, request: Request, user=Depends(guard("miaoying.overview"))): return invoke(request, request.app.state.miaoying_service.update_settings, payload.model_dump(), user)
    @router.post("/settings/test")
    def test_notification(payload: MiaoyingWebhookTest, request: Request, user=Depends(guard("miaoying.overview"))): return invoke(request, request.app.state.miaoying_service.test_notification, payload.model_dump(), user)
    @router.get("/overview")
    def overview(request: Request, user=Depends(guard("miaoying.overview"))): return invoke(request, request.app.state.miaoying_service.get_overview, user)
    @router.get("/tasks")
    def tasks(request: Request, user=Depends(guard(("miaoying.overview","miaoying.auto")))): return invoke(request, request.app.state.miaoying_service.list_tasks, user)
    @router.post("/tasks")
    def create_task(payload: MiaoyingTaskPayload, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.create_task, payload.model_dump(), user)
    @router.post("/tasks/batch-state")
    def batch_state(payload: MiaoyingBatchState, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.batch_set_task_state, payload.ids, payload.enabled, user)
    @router.post("/tasks/batch-delete")
    def batch_delete(payload: MiaoyingBatchDelete, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.batch_delete_tasks, payload.ids, user)
    @router.put("/tasks/{task_id}")
    def update_task(task_id: int, payload: MiaoyingTaskPayload, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.update_task, task_id, payload.model_dump(), user)
    @router.delete("/tasks/{task_id}")
    def delete_task(task_id: int, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.delete_task, task_id, user)
    @router.post("/tasks/{task_id}/run")
    def run_task(task_id: int, request: Request, user=Depends(guard("miaoying.auto"))): return invoke(request, request.app.state.miaoying_service.run_task, task_id, user)
    @router.get("/runs")
    def runs(request: Request, limit: int=Query(100,ge=1,le=500), user=Depends(guard(("miaoying.runs","miaoying.logs","miaoying.overview")))): return invoke(request, request.app.state.miaoying_service.list_runs, user, limit)
    @router.get("/submission-audits")
    def submission_audits(request: Request, limit: int=Query(100,ge=1,le=500), user=Depends(guard("miaoying.logs"))): return invoke(request, request.app.state.miaoying_service.list_submission_audits, user, limit)
    return router
