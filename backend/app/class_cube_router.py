from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from .class_cube_models import (
    ClassCubeAccountUpdate,
    QrSessionCreate,
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


def create_class_cube_router(auth_dependency) -> APIRouter:
    router = APIRouter(
        prefix="/api/class-cube",
        tags=["class-cube"],
    )

    @router.post("/qr-sessions")
    def create_qr_session(
        request: Request,
        payload: QrSessionCreate | None = None,
        actor=Depends(auth_dependency),
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
        actor=Depends(auth_dependency),
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
        actor=Depends(auth_dependency),
    ):
        return _invoke(
            request,
            _service(request).list_accounts,
            actor,
            owner_user_id=owner_user_id,
        )

    @router.put("/accounts/{account_id}")
    def update_account(
        account_id: int,
        payload: ClassCubeAccountUpdate,
        request: Request,
        actor=Depends(auth_dependency),
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
        actor=Depends(auth_dependency),
    ):
        return _invoke(
            request,
            _service(request).delete_account,
            account_id,
            actor,
        )

    @router.post("/accounts/{account_id}/courses/sync")
    def sync_courses(
        account_id: int,
        request: Request,
        actor=Depends(auth_dependency),
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
        actor=Depends(auth_dependency),
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
        actor=Depends(auth_dependency),
    ):
        return _invoke(
            request,
            _service(request).sync_items,
            course_id,
            actor,
        )

    @router.get("/courses/{course_id}/items")
    def list_items(
        course_id: int,
        request: Request,
        actor=Depends(auth_dependency),
    ):
        return _invoke(
            request,
            _service(request).list_items,
            course_id,
            actor,
        )

    return router
