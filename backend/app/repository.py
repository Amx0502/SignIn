import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .database import Database
from .db_models import AccountProjectRow, AccountRow, TaskRow


class AccountIndexError(IndexError):
    pass


class TaskIndexError(IndexError):
    pass


class DuplicateMobileError(ValueError):
    pass


def _normalize_account(data: dict | None = None) -> dict:
    data = data or {}
    return {
        "name": str(data.get("name", "")).strip(),
        "mobile": str(data.get("mobile", "")).strip(),
        "password": str(data.get("password", "")),
        "token": str(data.get("token", "")).strip(),
    }


def _normalize_task(data: dict | None = None) -> dict:
    data = data or {}
    raw_times = data.get("times", [])
    times = raw_times if isinstance(raw_times, list) else []
    raw_paths = data.get("pic_path", [])
    pic_paths = raw_paths if isinstance(raw_paths, list) else ([raw_paths] if raw_paths else [])
    return {
        "index": int(data.get("index", 1) or 1),
        "title": str(data.get("title", "")).strip() or f"任务{data.get('index', 1)}",
        "times": [str(item) for item in times],
        "enable": bool(data.get("enable", True)),
        "use_location": bool(data.get("use_location", False)),
        "text": str(data.get("text", "")),
        "pic_path": [str(item) for item in pic_paths if str(item)],
        "skip_weekends": bool(data.get("skip_weekends", False)),
        "mode": str(data.get("mode", "normal")),
        "notify_wechat": bool(data.get("notify_wechat", True)),
    }


class AccountRepository:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _task_to_dict(row: TaskRow) -> dict:
        return {
            "index": row.project_index,
            "title": row.title,
            "times": list(row.times or []),
            "enable": row.enable,
            "use_location": row.use_location,
            "text": row.text,
            "pic_path": list(row.pic_paths or []),
            "skip_weekends": row.skip_weekends,
            "mode": row.mode,
            "notify_wechat": row.notify_wechat,
        }

    @classmethod
    def _account_to_dict(cls, row: AccountRow) -> dict:
        return {
            "name": row.name,
            "mobile": row.mobile,
            "password": row.password,
            "token": row.token,
            "tasks": [cls._task_to_dict(task) for task in row.tasks],
            "projects": [dict(project.payload) for project in row.projects],
        }

    @staticmethod
    def _resolve_account(session: Session, index: int) -> AccountRow:
        if index < 0:
            raise AccountIndexError(index)
        row = session.scalar(
            select(AccountRow)
            .options(selectinload(AccountRow.tasks), selectinload(AccountRow.projects))
            .order_by(AccountRow.id)
            .offset(index)
            .limit(1)
        )
        if row is None:
            raise AccountIndexError(index)
        return row

    @staticmethod
    def _is_duplicate_key(exc: IntegrityError) -> bool:
        original = getattr(exc, "orig", None)
        return bool(getattr(original, "args", None) and original.args[0] == 1062)

    def list_accounts(self) -> list[dict]:
        with self.database.session() as session:
            rows = session.scalars(
                select(AccountRow)
                .options(selectinload(AccountRow.tasks), selectinload(AccountRow.projects))
                .order_by(AccountRow.id)
            ).all()
            return [self._account_to_dict(row) for row in rows]

    def add_account(self, data: dict) -> dict:
        account = _normalize_account(data)
        try:
            with self.database.session() as session:
                row = AccountRow(**account)
                session.add(row)
                session.flush()
                return self._account_to_dict(row)
        except IntegrityError as exc:
            if self._is_duplicate_key(exc):
                raise DuplicateMobileError("手机号已存在") from exc
            raise

    def update_account(self, account_index: int, data: dict) -> dict:
        account = _normalize_account(data)
        try:
            with self.database.session() as session:
                row = self._resolve_account(session, account_index)
                row.name = account["name"]
                row.mobile = account["mobile"]
                row.password = account["password"]
                row.token = account["token"]
                session.flush()
                return self._account_to_dict(row)
        except IntegrityError as exc:
            if self._is_duplicate_key(exc):
                raise DuplicateMobileError("手机号已存在") from exc
            raise

    def delete_account(self, account_index: int) -> None:
        with self.database.session() as session:
            row = self._resolve_account(session, account_index)
            session.delete(row)
