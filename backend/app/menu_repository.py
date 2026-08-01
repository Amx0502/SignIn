from typing import Any

from sqlalchemy import delete, select, update

from .auth_models import (
    MenuConfigAuditLogRow,
    MenuConfigRow,
    MenuConfigStateRow,
    UserMenuOverrideRow,
    UserRow,
)
from .menu_catalog import MENU_CATALOG, MENU_KEYS, build_effective_menu, catalog_tree


class MenuVersionConflictError(RuntimeError):
    def __init__(self, current_version: int):
        super().__init__("菜单配置已被其他管理员修改，请刷新后重试")
        self.current_version = current_version


class MenuRepository:
    def __init__(self, database):
        self.database = database

    def initialize(self) -> None:
        with self.database.session() as session:
            if session.get(MenuConfigStateRow, 1) is None:
                session.add(MenuConfigStateRow(id=1, version=1))
            existing = set(session.scalars(select(MenuConfigRow.menu_key)).all())
            for item in MENU_CATALOG:
                if item["key"] not in existing:
                    session.add(MenuConfigRow(menu_key=item["key"], visible=True))

    def current_version(self) -> int:
        with self.database.session() as session:
            state = session.get(MenuConfigStateRow, 1)
            return int(state.version if state else 1)

    @staticmethod
    def _global_visibility(session) -> dict[str, bool]:
        return {
            row.menu_key: bool(row.visible)
            for row in session.scalars(select(MenuConfigRow)).all()
        }

    @staticmethod
    def _user_overrides(session, user_id: int) -> dict[str, bool]:
        return {
            row.menu_key: bool(row.visible)
            for row in session.scalars(
                select(UserMenuOverrideRow).where(
                    UserMenuOverrideRow.user_id == user_id
                )
            ).all()
        }

    @staticmethod
    def _validate_keys(values: dict[str, Any]) -> None:
        unknown = set(values) - MENU_KEYS
        if unknown:
            raise ValueError(f"未知菜单项: {', '.join(sorted(unknown))}")

    @staticmethod
    def _bump_version(session, expected_version: int) -> int:
        result = session.execute(
            update(MenuConfigStateRow)
            .where(
                MenuConfigStateRow.id == 1,
                MenuConfigStateRow.version == expected_version,
            )
            .values(version=expected_version + 1)
        )
        if result.rowcount != 1:
            current = session.scalar(
                select(MenuConfigStateRow.version).where(MenuConfigStateRow.id == 1)
            )
            raise MenuVersionConflictError(int(current or 1))
        return expected_version + 1

    @staticmethod
    def _assert_version(session, expected_version: int) -> None:
        current = session.scalar(
            select(MenuConfigStateRow.version).where(MenuConfigStateRow.id == 1)
        )
        if int(current or 1) != expected_version:
            raise MenuVersionConflictError(int(current or 1))

    def _record_audit(
        self,
        session,
        *,
        actor_user_id: int,
        target_type: str,
        target_user_id: int | None,
        before: dict[str, Any],
        after: dict[str, Any],
        version: int,
    ) -> None:
        session.add(
            MenuConfigAuditLogRow(
                actor_user_id=actor_user_id,
                target_type=target_type,
                target_user_id=target_user_id,
                before_payload=before,
                after_payload=after,
                version=version,
            )
        )

    def update_global(
        self,
        *,
        expected_version: int,
        visibility: dict[str, bool],
        actor_user_id: int,
    ) -> dict[str, Any]:
        self._validate_keys(visibility)
        if any(type(value) is not bool for value in visibility.values()):
            raise ValueError("菜单显示状态必须是布尔值")
        with self.database.session() as session:
            current = self._global_visibility(session)
            changed = {
                key: visible
                for key, visible in visibility.items()
                if current.get(key, True) != visible
            }
            if not changed:
                self._assert_version(session, expected_version)
                return {"version": expected_version, "visibility": current}
            before = {key: current.get(key, True) for key in changed}
            version = self._bump_version(session, expected_version)
            for key, visible in changed.items():
                row = session.get(MenuConfigRow, key)
                if row is None:
                    session.add(MenuConfigRow(menu_key=key, visible=visible))
                else:
                    row.visible = visible
            self._record_audit(
                session,
                actor_user_id=actor_user_id,
                target_type="global",
                target_user_id=None,
                before=before,
                after=dict(changed),
                version=version,
            )
            return {"version": version, "visibility": {**current, **visibility}}

    def update_user_overrides(
        self,
        *,
        expected_version: int,
        user_id: int,
        overrides: dict[str, str],
        actor_user_id: int,
    ) -> dict[str, Any]:
        self._validate_keys(overrides)
        allowed = {"inherit", "visible", "hidden"}
        if any(value not in allowed for value in overrides.values()):
            raise ValueError("用户菜单覆盖状态无效")
        with self.database.session() as session:
            user = session.get(UserRow, user_id)
            if user is None or user.role != "user":
                raise ValueError("只能为普通用户设置菜单覆盖")
            current = self._user_overrides(session, user_id)
            requested_before = {
                key: (
                    "inherit"
                    if key not in current
                    else "visible" if current[key] else "hidden"
                )
                for key in overrides
            }
            changed = {
                key: state
                for key, state in overrides.items()
                if requested_before[key] != state
            }
            if not changed:
                self._assert_version(session, expected_version)
                return {"version": expected_version, "overrides": dict(overrides)}
            before = {key: requested_before[key] for key in changed}
            version = self._bump_version(session, expected_version)
            for key, state in changed.items():
                row = session.get(UserMenuOverrideRow, (user_id, key))
                if state == "inherit":
                    if row is not None:
                        session.delete(row)
                    continue
                visible = state == "visible"
                if row is None:
                    session.add(
                        UserMenuOverrideRow(
                            user_id=user_id,
                            menu_key=key,
                            visible=visible,
                        )
                    )
                else:
                    row.visible = visible
            self._record_audit(
                session,
                actor_user_id=actor_user_id,
                target_type="user",
                target_user_id=user_id,
                before=before,
                after=dict(changed),
                version=version,
            )
            return {"version": version, "overrides": dict(overrides)}

    def effective_catalog(self, user: dict[str, Any]) -> dict[str, Any]:
        with self.database.session() as session:
            state = session.get(MenuConfigStateRow, 1)
            global_visibility = self._global_visibility(session)
            overrides = (
                {}
                if user.get("role") == "admin"
                else self._user_overrides(session, int(user["id"]))
            )
            return {
                "version": int(state.version if state else 1),
                "menus": build_effective_menu(
                    global_visibility,
                    overrides,
                    user.get("role") == "admin",
                ),
            }

    def admin_config(self, user_id: int | None = None) -> dict[str, Any]:
        with self.database.session() as session:
            state = session.get(MenuConfigStateRow, 1)
            global_visibility = self._global_visibility(session)
            raw_overrides = self._user_overrides(session, user_id) if user_id else {}
            overrides = {
                key: (
                    "inherit"
                    if key not in raw_overrides
                    else "visible" if raw_overrides[key] else "hidden"
                )
                for key in MENU_KEYS
            }
            return {
                "version": int(state.version if state else 1),
                "catalog": catalog_tree(),
                "global": {key: global_visibility.get(key, True) for key in MENU_KEYS},
                "user_id": user_id,
                "overrides": overrides,
            }

    def is_menu_visible(self, user: dict[str, Any], menu_key: str) -> bool:
        self._validate_keys({menu_key: True})
        catalog = self.effective_catalog(user)

        def contains(items):
            return any(
                item["key"] == menu_key or contains(item.get("children") or [])
                for item in items
            )

        return contains(catalog["menus"])

    def list_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.database.session() as session:
            rows = session.scalars(
                select(MenuConfigAuditLogRow)
                .order_by(MenuConfigAuditLogRow.id.desc())
                .limit(max(1, min(limit, 500)))
            ).all()
            return [
                {
                    "id": row.id,
                    "actor_user_id": row.actor_user_id,
                    "target_type": row.target_type,
                    "target_user_id": row.target_user_id,
                    "before": row.before_payload,
                    "after": row.after_payload,
                    "version": row.version,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
