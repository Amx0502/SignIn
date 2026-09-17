import datetime as dt
import json
from pathlib import Path

from sqlalchemy import case, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .database import Database
from .db_models import AccountProjectRow, AccountRow, TaskRow, XxqdTaskRunRow
from .auth_models import UserFeaturePolicyRow, UserRow
from .task_date_schedule import get_last_effective_occurrence, normalize_task_date_rule


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


def _normalize_fill_values(raw) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    values: dict[str, str] = {}
    for key, val in raw.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        text = "" if val is None else str(val).strip()
        if text:
            values[key_str] = text
    return values


def _normalize_fill_fields(raw) -> list[str] | None:
    """None 表示未配置（沿用检测到的全部必填项）；列表表示用户勾选的提交项。"""
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return None
    fields: list[str] = []
    for item in raw:
        try:
            key = str(int(item))
        except (TypeError, ValueError):
            continue
        if key not in fields:
            fields.append(key)
    return fields


def _normalize_task(data: dict | None = None) -> dict:
    data = data or {}
    raw_times = data.get("times", [])
    times = raw_times if isinstance(raw_times, list) else []
    raw_paths = data.get("pic_path", [])
    pic_paths = raw_paths if isinstance(raw_paths, list) else ([raw_paths] if raw_paths else [])
    date_rule = normalize_task_date_rule(data)
    location_latitude = data.get("location_latitude")
    location_longitude = data.get("location_longitude")
    try:
        location_latitude = (
            float(location_latitude)
            if location_latitude is not None
            else None
        )
        location_longitude = (
            float(location_longitude)
            if location_longitude is not None
            else None
        )
    except (TypeError, ValueError):
        location_latitude = None
        location_longitude = None
    if (
        location_latitude is None
        or location_longitude is None
        or not -90 <= location_latitude <= 90
        or not -180 <= location_longitude <= 180
    ):
        location_latitude = None
        location_longitude = None
    return {
        "index": int(data.get("index", 1) or 1),
        "title": str(data.get("title", "")).strip() or f"任务{data.get('index', 1)}",
        "times": [str(item) for item in times],
        "enable": bool(data.get("enable", True)),
        "use_location": bool(data.get("use_location", False))
        or location_latitude is not None,
        "location_address": str(data.get("location_address", "")).strip(),
        "location_latitude": location_latitude,
        "location_longitude": location_longitude,
        "text": str(data.get("text", "")),
        "fill_name": str(data.get("fill_name", "")).strip(),
        "fill_values": _normalize_fill_values(data.get("fill_values")),
        "fill_fields": _normalize_fill_fields(data.get("fill_fields")),
        "pic_path": [str(item) for item in pic_paths if str(item)],
        "skip_weekends": bool(data.get("skip_weekends", False)),
        **date_rule,
        "auto_disable_after_finish": bool(
            data.get("auto_disable_after_finish", False)
        ),
        "mode": str(data.get("mode", "normal")),
        "notify_wechat": bool(data.get("notify_wechat", True)),
    }


class AccountRepository:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _task_to_dict(row: TaskRow) -> dict:
        return {
            "id": row.id,
            "index": row.project_index,
            "title": row.title,
            "times": list(row.times or []),
            "enable": row.enable,
            "use_location": row.use_location,
            "location_address": row.location_address or "",
            "location_latitude": row.location_latitude,
            "location_longitude": row.location_longitude,
            "text": row.text,
            "fill_name": row.fill_name or "",
            "fill_values": dict(row.fill_values or {}),
            "fill_fields": (
                list(row.fill_fields) if row.fill_fields is not None else None
            ),
            "pic_path": list(row.pic_paths or []),
            "skip_weekends": row.skip_weekends,
            "date_mode": row.date_mode or "daily",
            "run_dates": list(row.run_dates or []),
            "skip_dates": list(row.skip_dates or []),
            "auto_disable_after_finish": row.auto_disable_after_finish,
            "completed_at": (
                row.completed_at.isoformat(timespec="seconds")
                if row.completed_at else None
            ),
            "completion_result": row.completion_result or "",
            "completed_scheduled_for": (
                row.completed_scheduled_for.isoformat(timespec="seconds")
                if row.completed_scheduled_for else None
            ),
            "mode": row.mode,
            "notify_wechat": row.notify_wechat,
        }

    @classmethod
    def _account_to_dict(cls, row: AccountRow) -> dict:
        return {
            "id": row.id,
            "owner_user_id": row.owner_user_id,
            "name": row.name,
            "mobile": row.mobile,
            "password": row.password,
            "token": row.token,
            "tasks": [cls._task_to_dict(task) for task in row.tasks],
            "projects": [dict(project.payload) for project in row.projects],
        }

    @staticmethod
    def _run_to_dict(row: XxqdTaskRunRow) -> dict:
        return {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
        }

    def record_run(
        self,
        *,
        account: dict,
        task: dict,
        source: str,
        status: str,
        message: str,
        response_summary: dict,
        started_at: dt.datetime,
    ) -> dict:
        now = dt.datetime.now()
        safe_summary = json.loads(json.dumps(response_summary or {}, default=str))
        with self.database.session() as session:
            row = XxqdTaskRunRow(
                account_id=account.get("id"),
                owner_user_id=account.get("owner_user_id"),
                task_id=task.get("id"),
                account_name=str(account.get("name") or account.get("mobile") or "未知账号")[:255],
                task_title=str(task.get("title") or "未命名任务")[:255],
                source=str(source or "manual")[:32],
                mode=str(task.get("mode") or "normal")[:32],
                status=str(status or "failed")[:32],
                message=" ".join(str(message or "").split())[:500],
                response_summary=safe_summary,
                started_at=started_at,
                finished_at=now,
            )
            session.add(row)
            session.flush()
            return self._run_to_dict(row)

    def dashboard_summary(self, start_at: dt.datetime, end_at: dt.datetime) -> dict:
        success_statuses = ("success", "already_signed")
        failed_statuses = ("failed", "error", "unknown_result")
        with self.database.session() as session:
            account_count = int(session.scalar(select(func.count(AccountRow.id))) or 0)
            task_count = int(session.scalar(select(func.count(TaskRow.id))) or 0)
            enabled_task_count = int(session.scalar(
                select(func.count(TaskRow.id)).where(TaskRow.enable.is_(True))
            ) or 0)
            base = (XxqdTaskRunRow.started_at >= start_at, XxqdTaskRunRow.started_at < end_at)
            counts = session.execute(select(
                func.count(XxqdTaskRunRow.id),
                func.sum(case((XxqdTaskRunRow.status.in_(success_statuses), 1), else_=0)),
                func.sum(case((XxqdTaskRunRow.status.in_(failed_statuses), 1), else_=0)),
            ).where(*base)).one()
            recent_rows = session.scalars(
                select(XxqdTaskRunRow).where(*base)
                .order_by(desc(XxqdTaskRunRow.started_at), desc(XxqdTaskRunRow.id)).limit(20)
            ).all()
            type_rows = session.execute(
                select(XxqdTaskRunRow.mode, func.count(XxqdTaskRunRow.id))
                .where(*base).group_by(XxqdTaskRunRow.mode)
            ).all()
            rank_rows = session.execute(
                select(XxqdTaskRunRow.account_name, func.count(XxqdTaskRunRow.id))
                .where(*base, XxqdTaskRunRow.status.in_(success_statuses))
                .group_by(XxqdTaskRunRow.account_name)
                .order_by(desc(func.count(XxqdTaskRunRow.id))).limit(10)
            ).all()
            return {
                "accounts": account_count,
                "tasks": task_count,
                "enabled_tasks": enabled_task_count,
                "executions": int(counts[0] or 0),
                "success": int(counts[1] or 0),
                "failed": int(counts[2] or 0),
                "recent_runs": [self._run_to_dict(row) for row in recent_rows],
                "types": [{"mode": mode or "normal", "value": int(value)} for mode, value in type_rows],
                "ranking": [{"name": name or "未知账号", "value": int(value)} for name, value in rank_rows],
            }

    def list_runs(
        self,
        *,
        owner_user_id: int | None = None,
        is_admin: bool = True,
        account_id: int | None = None,
        task_id: int | None = None,
        status: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        with self.database.session() as session:
            conditions = []
            if owner_user_id is not None:
                conditions.append(
                    XxqdTaskRunRow.owner_user_id == owner_user_id
                )
            if account_id is not None:
                conditions.append(XxqdTaskRunRow.account_id == account_id)
            if task_id is not None:
                conditions.append(XxqdTaskRunRow.task_id == task_id)
            if status:
                conditions.append(XxqdTaskRunRow.status == status)
            if source:
                conditions.append(XxqdTaskRunRow.source == source)
            total = int(session.scalar(
                select(func.count(XxqdTaskRunRow.id)).where(*conditions)
            ) or 0)
            rows = session.scalars(
                select(XxqdTaskRunRow)
                .where(*conditions)
                .order_by(
                    desc(XxqdTaskRunRow.started_at),
                    desc(XxqdTaskRunRow.id),
                )
                .offset(max(int(offset), 0))
                .limit(min(max(int(limit), 1), 200))
            ).all()
            return {
                "total": total,
                "items": [self._run_to_dict(row) for row in rows],
            }

    @staticmethod
    def _resolve_account(
        session: Session,
        index: int,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> AccountRow:
        if index < 0:
            raise AccountIndexError(index)
        query = (
            select(AccountRow)
            .options(selectinload(AccountRow.tasks), selectinload(AccountRow.projects))
            .order_by(AccountRow.id)
        )
        if not is_admin and owner_user_id is not None:
            query = query.where(AccountRow.owner_user_id == owner_user_id)
        row = session.scalar(query.offset(index).limit(1))
        if row is None:
            raise AccountIndexError(index)
        return row

    @staticmethod
    def _is_duplicate_key(exc: IntegrityError) -> bool:
        original = getattr(exc, "orig", None)
        return bool(getattr(original, "args", None) and original.args[0] == 1062)

    def list_accounts(
        self,
        owner_user_id: int | None = None,
        is_admin: bool = True,
        active_owners_only: bool = False,
    ) -> list[dict]:
        with self.database.session() as session:
            query = (
                select(AccountRow)
                .options(selectinload(AccountRow.tasks), selectinload(AccountRow.projects))
                .order_by(AccountRow.id)
            )
            if not is_admin and owner_user_id is not None:
                query = query.where(AccountRow.owner_user_id == owner_user_id)
            if active_owners_only:
                query = query.outerjoin(
                    UserRow, UserRow.id == AccountRow.owner_user_id
                ).where(
                    (AccountRow.owner_user_id.is_(None))
                    | (
                        (UserRow.is_active.is_(True))
                        & (
                            (UserRow.expires_at.is_(None))
                            | (UserRow.expires_at > dt.datetime.now())
                        )
                        & (UserRow.card_used_at.is_(None))
                    )
                )
            rows = session.scalars(query).all()
            return [self._account_to_dict(row) for row in rows]

    def count_accounts(self, owner_user_id: int) -> int:
        with self.database.session() as session:
            return int(session.scalar(
                select(func.count(AccountRow.id)).where(
                    AccountRow.owner_user_id == owner_user_id
                )
            ) or 0)

    def delete_accounts_by_owner(self, owner_user_id: int) -> int:
        with self.database.session() as session:
            rows = session.scalars(
                select(AccountRow).where(
                    AccountRow.owner_user_id == owner_user_id
                )
            ).all()
            for row in rows:
                session.delete(row)
            session.flush()
            return len(rows)

    def add_account(
        self,
        data: dict,
        owner_user_id: int | None = None,
        account_limit: int | None = None,
    ) -> dict:
        account = _normalize_account(data)
        try:
            with self.database.session() as session:
                existing = None
                if owner_user_id is not None and account["mobile"]:
                    existing = session.scalar(
                        select(AccountRow)
                        .options(
                            selectinload(AccountRow.tasks),
                            selectinload(AccountRow.projects),
                        )
                        .where(AccountRow.mobile == account["mobile"])
                        .with_for_update()
                    )
                    if existing is not None:
                        if existing.owner_user_id == owner_user_id:
                            return self._account_to_dict(existing)
                        if existing.owner_user_id is not None:
                            raise DuplicateMobileError(
                                "手机号已绑定其他用户，无法重复关联"
                            )
                if owner_user_id is not None and account_limit is not None:
                    session.scalar(
                        select(UserFeaturePolicyRow)
                        .where(UserFeaturePolicyRow.user_id == owner_user_id)
                        .with_for_update()
                    )
                    count = int(session.scalar(
                        select(func.count(AccountRow.id)).where(
                            AccountRow.owner_user_id == owner_user_id
                        )
                    ) or 0)
                    if count >= int(account_limit):
                        raise ValueError(
                            f"小小签到账号额度已满（{account_limit} 个），"
                            "请联系管理员调整额度"
                        )
                if existing is not None:
                    existing.owner_user_id = owner_user_id
                    session.flush()
                    return self._account_to_dict(existing)
                row = AccountRow(**account, owner_user_id=owner_user_id)
                session.add(row)
                session.flush()
                return self._account_to_dict(row)
        except IntegrityError as exc:
            if self._is_duplicate_key(exc):
                raise DuplicateMobileError("手机号已存在") from exc
            raise

    def update_account(
        self,
        account_index: int,
        data: dict,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> dict:
        account = _normalize_account(data)
        try:
            with self.database.session() as session:
                row = self._resolve_account(
                    session, account_index, owner_user_id, is_admin
                )
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

    def delete_account(
        self,
        account_index: int,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> None:
        with self.database.session() as session:
            row = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            session.delete(row)

    @staticmethod
    def _resolve_task(session: Session, account_id: int, task_index: int) -> TaskRow:
        if task_index < 0:
            raise TaskIndexError(task_index)
        row = session.scalar(
            select(TaskRow)
            .where(TaskRow.account_id == account_id)
            .order_by(TaskRow.position, TaskRow.id)
            .offset(task_index)
            .limit(1)
        )
        if row is None:
            raise TaskIndexError(task_index)
        return row

    @staticmethod
    def _apply_task(row: TaskRow, task: dict) -> None:
        row.project_index = task["index"]
        row.title = task["title"]
        row.times = task["times"]
        row.enable = task["enable"]
        row.use_location = task["use_location"]
        row.location_address = task["location_address"]
        row.location_latitude = task["location_latitude"]
        row.location_longitude = task["location_longitude"]
        row.text = task["text"]
        row.fill_name = task["fill_name"]
        row.fill_values = task["fill_values"]
        row.fill_fields = task.get("fill_fields")
        row.pic_paths = task["pic_path"]
        row.skip_weekends = task["skip_weekends"]
        row.date_mode = task["date_mode"]
        row.run_dates = task["run_dates"]
        row.skip_dates = task["skip_dates"]
        row.auto_disable_after_finish = task["auto_disable_after_finish"]
        row.mode = task["mode"]
        row.notify_wechat = task["notify_wechat"]
        if row.enable:
            row.completed_at = None
            row.completion_result = ""
            row.completed_scheduled_for = None

    def complete_task_if_final_occurrence(
        self,
        task_id: int,
        scheduled_for: dt.datetime,
        completion_result: str,
    ) -> dict | None:
        scheduled_for = scheduled_for.replace(microsecond=0, tzinfo=None)
        result_value = "success" if completion_result == "success" else "failed"
        with self.database.session() as session:
            row = session.scalar(
                select(TaskRow).where(TaskRow.id == task_id).with_for_update()
            )
            if (
                row is None
                or not row.enable
                or not row.auto_disable_after_finish
                or (row.date_mode or "daily") != "specific"
            ):
                return None

            current_task = self._task_to_dict(row)
            last_occurrence = get_last_effective_occurrence(current_task)
            if last_occurrence is None or last_occurrence != scheduled_for:
                return None

            row.enable = False
            row.completed_at = dt.datetime.now()
            row.completion_result = result_value
            row.completed_scheduled_for = scheduled_for
            session.flush()
            return self._task_to_dict(row)

    def add_task(
        self,
        account_index: int,
        data: dict,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> dict:
        task = _normalize_task(data)
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            position = session.scalar(
                select(func.count(TaskRow.id)).where(TaskRow.account_id == account.id)
            )
            row = TaskRow(account_id=account.id, position=int(position or 0))
            self._apply_task(row, task)
            session.add(row)
            session.flush()
            return self._task_to_dict(row)

    def update_task(
        self,
        account_index: int,
        task_index: int,
        data: dict,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> dict:
        task = _normalize_task(data)
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            row = self._resolve_task(session, account.id, task_index)
            self._apply_task(row, task)
            session.flush()
            return self._task_to_dict(row)

    def delete_task(
        self,
        account_index: int,
        task_index: int,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> None:
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            row = self._resolve_task(session, account.id, task_index)
            session.delete(row)
            session.flush()
            remaining = session.scalars(
                select(TaskRow)
                .where(TaskRow.account_id == account.id)
                .order_by(TaskRow.position, TaskRow.id)
                .with_for_update()
            ).all()
            for position, task_row in enumerate(remaining):
                task_row.position = position

    def task_positions(
        self,
        account_index: int,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> list[int]:
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            return list(
                session.scalars(
                    select(TaskRow.position)
                    .where(TaskRow.account_id == account.id)
                    .order_by(TaskRow.position)
                ).all()
            )

    def update_token(
        self,
        account_index: int,
        token: str,
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> dict:
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            account.token = str(token)
            session.flush()
            return self._account_to_dict(account)

    def update_token_by_mobile(self, mobile: str, token: str) -> bool:
        with self.database.session() as session:
            account = session.scalar(select(AccountRow).where(AccountRow.mobile == str(mobile)))
            if account is None:
                return False
            account.token = str(token)
            return True

    def replace_projects(
        self,
        account_index: int,
        projects: list[dict],
        owner_user_id: int | None = None,
        is_admin: bool = True,
    ) -> list[dict]:
        with self.database.session() as session:
            account = self._resolve_account(
                session, account_index, owner_user_id, is_admin
            )
            account.projects.clear()
            session.flush()
            for position, project in enumerate(projects):
                account.projects.append(
                    AccountProjectRow(position=position, payload=dict(project))
                )
            session.flush()
            return [dict(project.payload) for project in account.projects]

    def child_counts(self) -> dict[str, int]:
        with self.database.session() as session:
            return {
                "tasks": int(session.scalar(select(func.count(TaskRow.id))) or 0),
                "projects": int(
                    session.scalar(select(func.count(AccountProjectRow.id))) or 0
                ),
            }

    def import_legacy_json_if_empty(self, path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("accounts.json 必须是数组格式")

        with self.database.session() as session:
            existing = int(session.scalar(select(func.count(AccountRow.id))) or 0)
            if existing:
                return 0

            for raw_account in data:
                if not isinstance(raw_account, dict):
                    raise ValueError("accounts.json 中的账户必须是对象")
                account = _normalize_account(raw_account)
                row = AccountRow(**account)
                for position, raw_task in enumerate(raw_account.get("tasks", [])):
                    if not isinstance(raw_task, dict):
                        raise ValueError("accounts.json 中的任务必须是对象")
                    task = _normalize_task(raw_task)
                    task_row = TaskRow(position=position)
                    self._apply_task(task_row, task)
                    row.tasks.append(task_row)
                projects = raw_account.get("projects", [])
                if not isinstance(projects, list):
                    raise ValueError("accounts.json 中的 projects 必须是数组")
                for position, project in enumerate(projects):
                    if not isinstance(project, dict):
                        raise ValueError("accounts.json 中的项目必须是对象")
                    row.projects.append(
                        AccountProjectRow(position=position, payload=dict(project))
                    )
                session.add(row)
            session.flush()
            return len(data)
