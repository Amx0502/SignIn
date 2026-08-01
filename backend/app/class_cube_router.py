from collections.abc import Callable

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse

from .class_cube_models import (
    ClassCubeAccountBatchDelete,
    ClassCubeAccountUpdate,
    ManualCheckinRequest,
    QrSessionCreate,
    ClassCubeTaskCreate,
    ClassCubeTaskUpdate,
    ClassCubeTaskBatchDelete,
    ClassCubeSettingsUpdate,
)
from .class_cube_repository import ClassCubeNotFound
from .class_cube_service import (
    ClassCubeRemoteError,
    ClassCubeValidationError,
)


def _success(data=None) -> dict:
    return {"ok": True, "data": data}


def _service(request: Request):
    return request.app.state.class_cube_service


def _invoke(
    request: Request,
    operation: Callable,
    *args,
    **kwargs,
):
    try:
        return _success(operation(*args, **kwargs))
    except ClassCubeNotFound as exc:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": str(exc)},
        )
    except ClassCubeValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )
    except ClassCubeRemoteError as exc:
        content = {
            "ok": False,
            "error": exc.message,
            "retryable": exc.retryable,
        }
        if exc.data:
            content["data"] = exc.data
        return JSONResponse(status_code=502, content=content)
    except Exception as exc:
        logger = getattr(
            request.app.state.class_cube_service,
            "logger",
            None,
        )
        if logger is not None:
            try:
                logger.error(
                    "班级魔方接口内部错误（%s）",
                    type(exc).__name__,
                )
            except Exception:
                pass
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "班级魔方服务内部错误",
            },
        )


def create_class_cube_router(auth_dependency, menu_dependency=None) -> APIRouter:
    router = APIRouter(
        prefix="/api/class-cube",
        tags=["class-cube"],
    )
    access_accounts = (
        menu_dependency("class_cube.accounts")
        if menu_dependency else auth_dependency
    )
    access_tasks = (
        menu_dependency("class_cube.tasks")
        if menu_dependency else auth_dependency
    )
    access_runs = (
        menu_dependency("class_cube.runs")
        if menu_dependency else auth_dependency
    )
    access_logs = (
        menu_dependency("class_cube.logs")
        if menu_dependency else auth_dependency
    )
    access_shared_read = (
        menu_dependency((
            "class_cube.overview",
            "class_cube.accounts",
            "class_cube.tasks",
            "class_cube.runs",
        ))
        if menu_dependency else auth_dependency
    )

    @router.get("/settings")
    def get_settings(
        request: Request,
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request, _service(request).get_settings, actor
        )

    @router.put("/settings")
    def update_settings(
        payload: ClassCubeSettingsUpdate,
        request: Request,
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request,
            _service(request).update_settings,
            payload.model_dump(),
            actor,
        )

    @router.post("/qr-sessions")
    def create_qr_session(
        request: Request,
        payload: QrSessionCreate | None = None,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).create_qr_session,
            actor,
            account_id=payload.account_id if payload else None,
        )

    @router.get("/qr-sessions/{token}")
    def poll_qr_session(
        token: str,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).poll_qr_session,
            token,
            actor,
        )

    @router.get("/accounts")
    def list_accounts(
        request: Request,
        owner_user_id: int | None = Query(
            default=None,
            gt=0,
        ),
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request,
            _service(request).list_accounts,
            actor,
            owner_user_id=owner_user_id,
        )

    @router.get("/logs")
    def get_logs(
        request: Request,
        limit: int = Query(default=200, ge=1, le=1000),
        actor=Depends(access_logs),
    ):
        return _success(request.app.state.class_cube_log_store.snapshot(limit))

    @router.put("/accounts/{account_id}")
    def update_account(
        account_id: int,
        payload: ClassCubeAccountUpdate,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).update_account,
            account_id,
            payload.model_dump(),
            actor,
        )

    @router.delete("/accounts/{account_id}")
    def delete_account(
        account_id: int,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).delete_account,
            account_id,
            actor,
        )

    @router.post("/accounts/batch-delete")
    def batch_delete_accounts(
        payload: ClassCubeAccountBatchDelete,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).batch_delete_accounts,
            payload.ids,
            actor,
        )

    @router.post("/accounts/{account_id}/courses/sync")
    def sync_courses(
        account_id: int,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).sync_courses,
            account_id,
            actor,
        )

    @router.get("/accounts/{account_id}/courses")
    def list_courses(
        account_id: int,
        request: Request,
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request,
            _service(request).list_courses,
            account_id,
            actor,
        )

    @router.post("/courses/{course_id}/items/sync")
    def sync_items(
        course_id: int,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).sync_items,
            course_id,
            actor,
            latest_only=True,
        )

    @router.get("/courses/{course_id}/items")
    def list_items(
        course_id: int,
        request: Request,
        latest_only: bool = Query(default=False),
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request,
            _service(request).list_items,
            course_id,
            actor,
            latest_only=latest_only,
        )

    @router.post("/items/{item_id}/checkin")
    def manual_checkin(
        item_id: int,
        payload: ManualCheckinRequest,
        request: Request,
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).tracked_manual_checkin,
            item_id,
            payload.model_dump(),
            actor,
        )

    @router.post("/photos")
    def upload_photo(
        request: Request,
        file: UploadFile = File(...),
        account_id: int | None = Query(
            default=None,
            gt=0,
        ),
        actor=Depends(access_accounts),
    ):
        return _invoke(
            request,
            _service(request).save_photo,
            file,
            actor,
            account_id=account_id,
        )

    @router.get("/tasks")
    def list_tasks(
        request: Request,
        owner_user_id: int | None = Query(default=None, gt=0),
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request, _service(request).list_tasks, actor,
            owner_user_id=owner_user_id,
        )

    @router.post("/tasks")
    def create_task(
        payload: ClassCubeTaskCreate,
        request: Request,
        actor=Depends(access_tasks),
    ):
        return _invoke(
            request, _service(request).create_task,
            payload.model_dump(), actor,
        )

    @router.put("/tasks/{task_id}")
    def update_task(
        task_id: int,
        payload: ClassCubeTaskUpdate,
        request: Request,
        actor=Depends(access_tasks),
    ):
        return _invoke(
            request, _service(request).update_task, task_id,
            payload.model_dump(exclude_unset=True), actor,
        )

    @router.delete("/tasks/{task_id}")
    def delete_task(
        task_id: int,
        request: Request,
        actor=Depends(access_tasks),
    ):
        return _invoke(
            request, _service(request).delete_task, task_id, actor
        )

    @router.post("/tasks/batch-delete")
    def batch_delete_tasks(
        payload: ClassCubeTaskBatchDelete,
        request: Request,
        actor=Depends(access_tasks),
    ):
        return _invoke(
            request, _service(request).batch_delete_tasks,
            payload.ids, actor,
        )

    @router.post("/tasks/{task_id}/run")
    def run_task_now(
        task_id: int,
        request: Request,
        actor=Depends(access_tasks),
    ):
        service = _service(request)
        actor_user_id, is_admin = service._actor_scope(actor)
        try:
            service.repository.get_task(
                task_id, actor_user_id, is_admin
            )
        except ClassCubeNotFound as exc:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": str(exc)},
            )
        return _invoke(
            request,
            service.execute_task,
            task_id,
            trigger="manual",
        )

    @router.get("/runs")
    def list_runs(
        request: Request,
        owner_user_id: int | None = Query(default=None, gt=0),
        account_id: int | None = Query(default=None, gt=0),
        course_id: int | None = Query(default=None, gt=0),
        task_id: int | None = Query(default=None, gt=0),
        status: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        actor=Depends(access_shared_read),
    ):
        return _invoke(
            request, _service(request).list_runs, actor,
            owner_user_id=owner_user_id,
            account_id=account_id,
            course_id=course_id,
            task_id=task_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    @router.post("/claims/{claim_id}/retry")
    def confirm_claim_retry(
        claim_id: int,
        request: Request,
        actor=Depends(access_runs),
    ):
        return _invoke(
            request, _service(request).confirm_claim_retry,
            claim_id, actor,
        )

    return router
