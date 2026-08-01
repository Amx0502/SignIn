from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .menu_events import MenuEventBroker
from .menu_models import GlobalMenuConfigUpdate, UserMenuOverrideUpdate
from .menu_repository import MenuVersionConflictError


def _success(data=None) -> dict:
    return {"ok": True, "data": data}


def _conflict(error: MenuVersionConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "ok": False,
            "error": str(error),
            "current_version": error.current_version,
        },
    )


def create_menu_guard(auth_dependency, get_repository: Callable):
    def require_menu(menu_key: str | tuple[str, ...]):
        menu_keys = (menu_key,) if isinstance(menu_key, str) else tuple(menu_key)

        async def dependency(user=Depends(auth_dependency)):
            repository = get_repository()
            if not any(
                repository.is_menu_visible(user, candidate)
                for candidate in menu_keys
            ):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "ok": False,
                        "error": "该功能已被管理员隐藏",
                        "menu_key": menu_keys[0],
                        "menu_keys": list(menu_keys),
                    },
                )
            return user

        return dependency

    return require_menu


def create_menu_router(
    auth_dependency,
    admin_dependency,
    get_repository: Callable,
    broker: MenuEventBroker,
) -> APIRouter:
    router = APIRouter(tags=["menu"])

    @router.get("/api/menu/catalog")
    def get_catalog(user=Depends(auth_dependency)):
        return _success(get_repository().effective_catalog(user))

    @router.get("/api/menu/events")
    async def menu_events(
        request: Request,
        last_version: int = Query(default=0, ge=0),
        _user=Depends(auth_dependency),
    ):
        async def stream():
            async for event in broker.subscribe(last_version=last_version):
                if await request.is_disconnected():
                    break
                yield event

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/api/admin/menu-config")
    def get_admin_config(
        user_id: int | None = Query(default=None, gt=0),
        _admin=Depends(admin_dependency),
    ):
        return _success(get_repository().admin_config(user_id))

    @router.put("/api/admin/menu-config/global")
    async def update_global(
        payload: GlobalMenuConfigUpdate,
        admin=Depends(admin_dependency),
    ):
        try:
            result = get_repository().update_global(
                expected_version=payload.version,
                visibility=payload.visibility,
                actor_user_id=admin["id"],
            )
        except MenuVersionConflictError as error:
            return _conflict(error)
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": str(error)},
            )
        await broker.publish(result["version"])
        return _success(result)

    @router.put("/api/admin/menu-config/users/{user_id}")
    async def update_user_overrides(
        user_id: int,
        payload: UserMenuOverrideUpdate,
        admin=Depends(admin_dependency),
    ):
        try:
            result = get_repository().update_user_overrides(
                expected_version=payload.version,
                user_id=user_id,
                overrides=payload.overrides,
                actor_user_id=admin["id"],
            )
        except MenuVersionConflictError as error:
            return _conflict(error)
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": str(error)},
            )
        await broker.publish(result["version"])
        return _success(result)

    @router.get("/api/admin/menu-config/logs")
    def list_audit_logs(
        limit: int = Query(default=100, ge=1, le=500),
        _admin=Depends(admin_dependency),
    ):
        return _success(get_repository().list_audit_logs(limit))

    return router
