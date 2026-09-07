import base64
import hashlib
import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from time import sleep

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import config
from .checkin_delay_settings import get_checkin_delay_range
from .miaoying_client import MiaoyingClient, MiaoyingRemoteError
from .miaoying_database import MiaoyingDatabase
from .miaoying_db_models import MiaoyingAccountRow, MiaoyingFormRow, MiaoyingQrSessionRow, MiaoyingRunRow, MiaoyingTaskRow
from .miaoying_notifier import MiaoyingNotificationError, MiaoyingNotifier
from .miaoying_settings import (
    MiaoyingSettingsError,
    load_miaoying_settings,
    save_miaoying_settings,
)


class MiaoyingValidationError(ValueError):
    pass


class MiaoyingNotFound(LookupError):
    pass


class MiaoyingService:
    def __init__(self, database: MiaoyingDatabase, client: MiaoyingClient):
        self.database = database
        self.client = client
        raw_key = config.MIAOYING_TOKEN_ENCRYPTION_KEY
        self.cipher = None
        if raw_key and raw_key != "replace-with-a-fernet-key":
            try:
                self.cipher = Fernet(raw_key.encode())
            except (ValueError, TypeError) as exc:
                raise RuntimeError("MIAOYING_TOKEN_ENCRYPTION_KEY 不是有效的 Fernet 密钥") from exc
        elif database.settings.password:
            derived = hashlib.sha256(
                ("signin:miaoying:" + database.settings.password).encode()
            ).digest()
            self.cipher = Fernet(base64.urlsafe_b64encode(derived))

    def close(self):
        self.client.close()

    @staticmethod
    def _owner(user: dict) -> int:
        return int(user["id"])

    @staticmethod
    def _is_admin(user: dict) -> bool:
        return user.get("role") == "admin"

    def _scope(self, stmt, model, user):
        return stmt if self._is_admin(user) else stmt.where(model.owner_user_id == self._owner(user))

    def _token(self, account: MiaoyingAccountRow) -> str:
        if self.cipher is None:
            raise MiaoyingValidationError("尚未配置秒应登录凭据加密密钥")
        try:
            return self.cipher.decrypt(account.token_ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise MiaoyingValidationError("秒应登录凭据无法解密，请重新扫码登录") from exc

    def create_qr(self, user: dict) -> dict:
        if self.cipher is None:
            raise MiaoyingValidationError("请先配置 MIAOYING_TOKEN_ENCRYPTION_KEY 再扫码登录")
        now = datetime.now()
        with self.database.session() as session:
            existing = session.scalar(
                select(MiaoyingQrSessionRow)
                .where(
                    MiaoyingQrSessionRow.owner_user_id == self._owner(user),
                    MiaoyingQrSessionRow.status == "waiting",
                    # 不复用即将过期的二维码，避免刚显示就失效。
                    MiaoyingQrSessionRow.expires_at > now + timedelta(seconds=20),
                    # 旧版本创建过 5 分钟会话；切换到 2 分钟后不再复用。
                    MiaoyingQrSessionRow.expires_at <= now + timedelta(minutes=2),
                )
                .order_by(MiaoyingQrSessionRow.created_at.desc())
                .limit(1)
            )
            if existing:
                return {
                    "id": existing.id,
                    "qr_content": existing.qr_content,
                    "expires_at": existing.expires_at,
                    "status": "waiting",
                }

        remote = self.client.create_qr().get("data") or {}
        scene_id, content = str(remote.get("sceneId") or ""), str(remote.get("url") or "")
        if not scene_id or not content:
            raise MiaoyingRemoteError("秒应未返回有效二维码")
        local_id = uuid.uuid4().hex
        expires_at = datetime.now() + timedelta(minutes=2)
        with self.database.session() as session:
            session.add(MiaoyingQrSessionRow(id=local_id, owner_user_id=self._owner(user), remote_scene_id=scene_id, qr_content=content, expires_at=expires_at))
        return {"id": local_id, "qr_content": content, "expires_at": expires_at, "status": "waiting"}

    def poll_qr(self, local_id: str, user: dict) -> dict:
        with self.database.session() as session:
            row = session.get(MiaoyingQrSessionRow, local_id)
            if not row or (row.owner_user_id != self._owner(user) and not self._is_admin(user)):
                raise MiaoyingNotFound("扫码会话不存在")
            if row.status == "completed":
                return {"status": "completed"}
            if row.expires_at < datetime.now():
                row.status = "expired"
                return {"status": "expired"}
            data = self.client.poll_qr(row.remote_scene_id)
            if not data:
                return {"status": "waiting", "expires_at": row.expires_at}
            token = str(data["token"])
            me = self.client.get_me(token)
            remote_uid = str(me.get("_id") or data.get("_id") or "")
            nickname = str(me.get("nickname") or data.get("nickname") or "秒应账号")
            if not remote_uid:
                raise MiaoyingRemoteError("扫码成功但未取得秒应用户 ID")
            account = session.scalar(select(MiaoyingAccountRow).where(MiaoyingAccountRow.remote_user_id == remote_uid))
            if account and account.owner_user_id != self._owner(user) and not self._is_admin(user):
                raise MiaoyingValidationError("该秒应账号已由其他后台用户绑定")
            if not account:
                account = MiaoyingAccountRow(owner_user_id=self._owner(user), remote_user_id=remote_uid, nickname=nickname, remark=nickname, token_ciphertext="")
                session.add(account)
            account.nickname = nickname
            account.token_ciphertext = self.cipher.encrypt(token.encode()).decode()
            account.status = "active"
            account.enabled = True
            account.last_verified_at = datetime.now()
            account.last_error = ""
            row.status = "completed"
            row.completed_at = datetime.now()
            session.flush()
            return {"status": "completed", "account": self._account_dict(account)}

    def list_accounts(self, user: dict) -> list[dict]:
        with self.database.session() as session:
            stmt = self._scope(select(MiaoyingAccountRow), MiaoyingAccountRow, user).order_by(MiaoyingAccountRow.updated_at.desc())
            return [self._account_dict(row) for row in session.scalars(stmt)]

    def update_account(self, account_id: int, payload: dict, user: dict) -> dict:
        with self.database.session() as session:
            row = self._get_account(session, account_id, user)
            for key, value in payload.items():
                setattr(row, key, value)
            row.updated_at = datetime.now()
            return self._account_dict(row)

    def delete_account(self, account_id: int, user: dict):
        with self.database.session() as session:
            session.delete(self._get_account(session, account_id, user))

    def sync_forms(self, account_id: int, user: dict) -> list[dict]:
        with self.database.session() as session:
            account = self._get_account(session, account_id, user)
            token = self._token(account)
            rows = self.client.get_tongjis(token, account.remote_user_id)
            known_ids = {str(item.get("_id") or "") for item in rows}
            for record in self.client.get_records(token, account.remote_user_id):
                remote_id = str(record.get("tongjiId") or "")
                if remote_id and remote_id not in known_ids:
                    rows.append({"_id": remote_id})
                    known_ids.add(remote_id)
            now = datetime.now()
            for item in rows:
                remote_id = str(item.get("_id") or "")
                if not remote_id:
                    continue
                row = session.scalar(select(MiaoyingFormRow).where(MiaoyingFormRow.account_id == account.id, MiaoyingFormRow.remote_tongji_id == remote_id))
                if not row:
                    row = MiaoyingFormRow(account_id=account.id, remote_tongji_id=remote_id)
                    session.add(row)
                detail = self.client.get_tongji(token, remote_id)
                merged = {**item, **detail}
                row.title = str(merged.get("title") or "未命名签到")
                row.content = str(merged.get("content") or "")
                row.is_closed = bool(merged.get("isClosed"))
                row.is_repeat = bool(merged.get("isRepeat"))
                row.requirements = self._requirements(merged)
                row.raw_snapshot = merged
                row.synced_at = now
            account.last_sync_at = now
            account.last_error = ""
            session.flush()
            form_rows = list(session.scalars(select(MiaoyingFormRow).where(MiaoyingFormRow.account_id == account.id)))
            return [self._form_dict(row) for row in self._sort_forms(form_rows)]

    def list_forms(self, account_id: int, user: dict) -> list[dict]:
        with self.database.session() as session:
            account = self._get_account(session, account_id, user)
            form_rows = list(session.scalars(select(MiaoyingFormRow).where(MiaoyingFormRow.account_id == account.id)))
            return [self._form_dict(row) for row in self._sort_forms(form_rows)]

    @classmethod
    def _sort_forms(cls, rows: list[MiaoyingFormRow]) -> list[MiaoyingFormRow]:
        return sorted(rows, key=lambda row: (cls._remote_form_time(row), row.id or 0), reverse=True)

    @staticmethod
    def _remote_form_time(row: MiaoyingFormRow) -> float:
        snapshot = row.raw_snapshot or {}
        value = snapshot.get("createdAt") or snapshot.get("updatedAt")
        if isinstance(value, (int, float)):
            return float(value) / 1000 if value > 10_000_000_000 else float(value)
        if isinstance(value, str):
            try:
                number = float(value)
                return number / 1000 if number > 10_000_000_000 else number
            except ValueError:
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    pass
        return row.synced_at.timestamp() if row.synced_at else 0

    def get_settings(self, user: dict) -> dict:
        try:
            settings = load_miaoying_settings()
        except MiaoyingSettingsError as exc:
            raise MiaoyingValidationError(str(exc)) from exc
        if not self._is_admin(user):
            settings.pop("miaoying_webhook_url", None)
        return settings

    def update_settings(self, payload: dict, user: dict) -> dict:
        if not self._is_admin(user):
            raise MiaoyingNotFound("秒应设置不存在")
        try:
            return save_miaoying_settings(payload.get("miaoying_webhook_url", ""))
        except MiaoyingSettingsError as exc:
            raise MiaoyingValidationError(str(exc)) from exc

    def manual_checkin(self, form_id: int, payload: dict, user: dict) -> dict:
        with self.database.session() as session:
            account = self._get_account(session, payload["account_id"], user)
            form = session.get(MiaoyingFormRow, form_id)
            if not form or form.account_id != account.id:
                raise MiaoyingValidationError("签到项目与账号不匹配")
            if not account.enabled or account.status != "active":
                raise MiaoyingValidationError("秒应账号不可用，请重新扫码")
            token = self._token(account)
            detail, records = self.client.get_checkin_context(
                token, form.remote_tongji_id, account.remote_user_id
            )
            requirements = self._requirements(detail)
            if requirements["unsupported"]:
                raise MiaoyingValidationError(
                    "该项目需要当前版本不支持的字段："
                    + "、".join(requirements["unsupported"])
                )
            if detail.get("isClosed"):
                raise MiaoyingValidationError("秒应项目已关闭")
            if not detail.get("isRepeat") and any(
                str(item.get("tongjiId")) == form.remote_tongji_id
                for item in records
            ):
                raise MiaoyingValidationError("该账号已提交此签到项目")
            latitude = payload.get("latitude")
            longitude = payload.get("longitude")
            if requirements["location"] and (latitude is None or longitude is None):
                raise MiaoyingValidationError("该项目要求位置，请先在地图中选择签到位置")
            submission = self._build_submission(
                account,
                form.remote_tongji_id,
                requirements,
                payload.get("answers") or {},
                payload.get("location_name"),
                latitude,
                longitude,
            )
            remote_id = self.client.submit(token, submission)
            notice = self._send_notification(
                account=account,
                form=form,
                status="success",
                message="签到成功",
                trigger="manual",
                latitude=latitude,
                longitude=longitude,
                enabled=bool(payload.get("notify_wecom", True)),
            )
            return {
                "status": "success",
                "message": "签到成功",
                "submission_id": remote_id,
                "notification": notice,
            }

    def list_tasks(self, user: dict) -> list[dict]:
        with self.database.session() as session:
            stmt = self._scope(select(MiaoyingTaskRow), MiaoyingTaskRow, user).order_by(MiaoyingTaskRow.updated_at.desc())
            return [self._task_dict(row) for row in session.scalars(stmt)]

    def create_task(self, payload: dict, user: dict) -> dict:
        with self.database.session() as session:
            account = self._get_account(session, payload["account_id"], user)
            form = session.get(MiaoyingFormRow, payload["form_id"])
            if not form or form.account_id != account.id:
                raise MiaoyingValidationError("签到项目与账号不匹配")
            payload["answer_schema"] = list((form.requirements or {}).get("fields") or [])
            row = MiaoyingTaskRow(owner_user_id=self._owner(user), **payload)
            session.add(row); session.flush()
            return self._task_dict(row)

    def update_task(self, task_id: int, payload: dict, user: dict) -> dict:
        with self.database.session() as session:
            row = self._get_task(session, task_id, user)
            form = session.get(MiaoyingFormRow, payload["form_id"])
            if not form or form.account_id != payload["account_id"]:
                raise MiaoyingValidationError("签到项目与账号不匹配")
            payload["answer_schema"] = list((form.requirements or {}).get("fields") or [])
            for key, value in payload.items(): setattr(row, key, value)
            row.updated_at = datetime.now(); session.flush()
            return self._task_dict(row)

    def delete_task(self, task_id: int, user: dict):
        with self.database.session() as session: session.delete(self._get_task(session, task_id, user))

    def list_runs(self, user: dict, limit: int = 100) -> list[dict]:
        with self.database.session() as session:
            stmt = self._scope(select(MiaoyingRunRow), MiaoyingRunRow, user).order_by(MiaoyingRunRow.started_at.desc()).limit(min(max(limit, 1), 500))
            return [self._run_dict(row) for row in session.scalars(stmt)]

    def dashboard_summary(self, start_at: datetime, end_at: datetime) -> dict:
        with self.database.session() as session:
            accounts = list(session.scalars(select(MiaoyingAccountRow)))
            tasks = list(session.scalars(select(MiaoyingTaskRow)))
            runs = list(session.scalars(select(MiaoyingRunRow).where(MiaoyingRunRow.started_at >= start_at, MiaoyingRunRow.started_at < end_at).order_by(MiaoyingRunRow.started_at.desc())))
            account_names = {row.id: row.remark or row.nickname for row in accounts}
            task_names = {row.id: row.name for row in tasks}
            success = sum(1 for row in runs if row.status == "success")
            failed = sum(1 for row in runs if row.status == "failed")
            ranking_counts: dict[str, int] = {}
            for row in runs:
                if row.status == "success":
                    name = account_names.get(row.account_id, "未知账号")
                    ranking_counts[name] = ranking_counts.get(name, 0) + 1
            return {
                "accounts": len(accounts), "tasks": len(tasks),
                "enabled_tasks": sum(1 for row in tasks if row.enabled),
                "executions": len(runs), "success": success, "failed": failed,
                "types": [{"mode":"miaoying","value":len(runs)}] if runs else [],
                "recent_runs": [{"id":row.id,"task_name":task_names.get(row.task_id,"秒应签到"),"account_name":account_names.get(row.account_id,"未知账号"),"mode":"miaoying","status":row.status,"started_at":row.started_at} for row in runs[:8]],
                "ranking": [{"name":name,"value":value} for name,value in sorted(ranking_counts.items(), key=lambda item:-item[1])],
            }

    def run_task(self, task_id: int, user: dict, trigger="manual") -> dict:
        with self.database.session() as session:
            task = self._get_task(session, task_id, user)
            return self._execute(session, task, trigger, f"{trigger}:{uuid.uuid4().hex}")

    def run_due_tasks(self):
        now = datetime.now(); today = now.date()
        with self.database.session() as session:
            tasks = list(session.scalars(select(MiaoyingTaskRow).where(MiaoyingTaskRow.enabled.is_(True))))
            for task in tasks:
                if not self._date_allowed(task, today): continue
                for configured in task.schedule_times or []:
                    try:
                        scheduled = datetime.combine(today, time.fromisoformat(str(configured)))
                    except ValueError:
                        continue
                    if not 0 <= (now - scheduled).total_seconds() < 20: continue
                    key = f"{today.isoformat()}T{str(configured)[:8]}"
                    if task.last_schedule_key == key: continue
                    task.last_schedule_key = key
                    try: self._execute(session, task, "scheduler", key)
                    except Exception: pass
                if task.auto_disable_after_finish and task.date_mode == "specific" and task.run_dates:
                    last = max(date.fromisoformat(value) for value in task.run_dates)
                    if today > last: task.enabled = False

    def _execute(self, session, task, trigger, schedule_key):
        account = session.get(MiaoyingAccountRow, task.account_id); form = session.get(MiaoyingFormRow, task.form_id)
        run = MiaoyingRunRow(owner_user_id=task.owner_user_id, task_id=task.id, account_id=task.account_id, form_id=task.form_id, schedule_key=schedule_key, trigger=trigger)
        try:
            with session.begin_nested():
                session.add(run)
                session.flush()
        except IntegrityError:
            return {"status":"skipped","message":"该时间点已被其他调度进程处理","task_id":task.id}
        try:
            if not account or not form: raise MiaoyingValidationError("任务关联数据不存在")
            if not account.enabled or account.status != "active": raise MiaoyingValidationError("秒应账号不可用，请重新扫码")
            minimum, maximum = get_checkin_delay_range("miaoying")
            delay = random.uniform(minimum, maximum)
            if delay > 0:
                sleep(delay)
            token = self._token(account)
            detail, records = self.client.get_checkin_context(
                token, form.remote_tongji_id, account.remote_user_id
            )
            requirements = self._requirements(detail)
            blocked = requirements["unsupported"]
            if blocked: raise MiaoyingValidationError("该项目需要当前版本不支持的字段：" + "、".join(blocked))
            if detail.get("isClosed"): raise MiaoyingValidationError("秒应项目已关闭")
            if not detail.get("isRepeat") and any(str(item.get("tongjiId")) == form.remote_tongji_id for item in records):
                raise MiaoyingValidationError("该账号已提交此签到项目")
            if requirements["location"] and (task.latitude is None or task.longitude is None):
                raise MiaoyingValidationError("该项目要求位置，请先配置经纬度")
            payload = self._build_submission(
                account,
                form.remote_tongji_id,
                requirements,
                task.answers or {},
                task.location_name,
                task.latitude,
                task.longitude,
            )
            remote_id = self.client.submit(token, payload)
            run.status="success"; run.remote_submission_id=remote_id; run.message="签到成功"; run.response_summary={"submission_id": remote_id}
            if not detail.get("isRepeat"):
                task.enabled = False
            elif task.auto_disable_after_finish and task.date_mode == "specific" and task.run_dates:
                last_date = max(date.fromisoformat(value) for value in task.run_dates)
                last_time = max(str(value)[:8] for value in (task.schedule_times or ["00:00:00"]))
                if datetime.now().date() >= last_date and datetime.now().strftime("%H:%M:%S") >= last_time:
                    task.enabled = False
        except Exception as exc:
            run.status="failed"; run.message=str(exc)[:1000]
        if account and form:
            self._send_notification(
                account=account,
                form=form,
                status=run.status,
                message=run.message,
                trigger=trigger,
                latitude=task.latitude,
                longitude=task.longitude,
            )
        run.finished_at=datetime.now(); session.flush()
        return self._run_dict(run)

    @staticmethod
    def _send_notification(
        *,
        account,
        form,
        status,
        message,
        trigger,
        latitude=None,
        longitude=None,
        enabled=True,
    ) -> dict:
        if not enabled:
            return {"sent": False, "reason": "disabled"}
        try:
            webhook = load_miaoying_settings().get("miaoying_webhook_url", "")
            if not webhook:
                return {"sent": False, "reason": "not_configured"}
            MiaoyingNotifier().send(
                webhook,
                account_name=account.remark or account.nickname,
                form_name=form.title,
                status=status,
                message=message,
                trigger=trigger,
                latitude=latitude,
                longitude=longitude,
            )
            return {"sent": True}
        except (MiaoyingSettingsError, MiaoyingNotificationError):
            return {"sent": False, "reason": "send_failed"}

    @classmethod
    def _requirements(cls, data):
        unsupported=[]
        flags=(("needWifi","Wi-Fi"),("needSignature","签名"))
        for key,label in flags:
            if data.get(key) and label not in unsupported: unsupported.append(label)
        media_flags=(("needImages","imageIsRequired","图片"),("needVideo","videoIsRequired","视频"),("needAudio","audioIsRequired","录音"))
        for enabled_key, required_key, label in media_flags:
            if data.get(enabled_key) and data.get(required_key) and label not in unsupported:
                unsupported.append(label)
        fields = cls._normalize_fields(data)
        supported_controls = {"text", "textarea", "single", "multiple", "select"}
        for field in fields:
            if field["required"] and field["control"] not in supported_controls:
                label = field["title"] or "复杂必填项"
                if label not in unsupported:
                    unsupported.append(label)
        return {
            "location": bool(data.get("needLocation") or data.get("needSubmitLocation")),
            # 秒应由项目创建者决定结果页是否公开详细位置。关闭时仍需提交
            # 精确经纬度，但秒应结果页通常只展示省、市。
            "location_detail_visible": bool(data.get("openLocationInfo")),
            "unsupported": unsupported,
            "fields": fields,
            "identity": {
                "class_label": str(data.get("groupLabelName") or "班级").strip(),
                "fixed": bool(data.get("fixedNo") or data.get("showNameList")),
                "roster": [
                    {"name": str(row.get("name") or ""), "no": row.get("no"),
                     "groupName": str(row.get("groupName") or ""),
                     "noLabel": str(row.get("noLabel") if row.get("noLabel") is not None else row.get("no", ""))}
                    for row in (data.get("nameList") or []) if isinstance(row, dict)
                ],
                "name_label": str(data.get("nameLabel") or "姓名").strip(),
                "number_label": str(data.get("noName") or "学号").strip(),
            },
        }

    @classmethod
    def _normalize_fields(cls, data: dict) -> list[dict]:
        fields: list[dict] = []
        required_titles = {
            str(item.get("title") if isinstance(item, dict) else item).strip()
            for item in (data.get("requiredFields") or [])
            if str(item.get("title") if isinstance(item, dict) else item).strip()
        }

        for index, raw in enumerate(data.get("infoForms") or []):
            if not isinstance(raw, dict) or raw.get("isRemove"):
                continue
            title = str(raw.get("title") or f"字段 {index + 1}").strip()
            fields.append(cls._normalize_field(raw, "info", index, title in required_titles))

        for index, raw in enumerate(data.get("optionFields") or []):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or f"选项 {index + 1}").strip()
            field = cls._normalize_field(raw, "option", index, title in required_titles)
            if not any(item["title"] == field["title"] for item in fields):
                fields.append(field)

        existing_titles = {field["title"] for field in fields}
        for index, title in enumerate(sorted(required_titles - existing_titles)):
            fields.append({
                "key": f"required:{index}:{title}",
                "id": "",
                "source": "required",
                "title": title,
                "description": "",
                "control": "text",
                "required": True,
                "options": [],
                "min_select": 1,
                "max_select": 1,
            })
        return fields

    @staticmethod
    def _normalize_field(raw: dict, source: str, index: int, forced_required: bool) -> dict:
        raw_type = str(raw.get("type") or "").lower()
        is_multi = bool(raw.get("isMulti")) or raw_type in {"14", "checkbox", "checkboxes", "multiple", "multi", "multiselect"}
        options = []
        raw_options = raw.get("options") or []
        if isinstance(raw_options, str):
            try:
                decoded = json.loads(raw_options)
                raw_options = decoded if isinstance(decoded, list) else [raw_options]
            except json.JSONDecodeError:
                raw_options = [raw_options]
        elif not isinstance(raw_options, list):
            raw_options = []
        for option_index, option in enumerate(raw_options):
            if isinstance(option, dict):
                label = str(option.get("label") or option.get("title") or option.get("name") or option.get("value") or "").strip()
                value = option.get("value", option.get("id", label))
            else:
                label = str(option).strip()
                value = option
            if label:
                options.append({
                    "label": label,
                    "value": str(value),
                    # 秒应新版 infoForms 的选项提交值不是显示文本，而是
                    # 该选项在 options 数组中的零基序号。
                    "submit_value": str(option_index) if source == "info" else str(value),
                })
        if bool(raw.get("isImage")):
            control = "unsupported"
        elif is_multi:
            control = "multiple"
        elif options or raw_type in {"1", "radio", "single", "select", "option"}:
            control = "single" if raw_type in {"1", "radio", "single", "option"} else "select"
        elif raw_type in {"textarea", "longtext"}:
            control = "textarea"
        elif raw_type in {"", "text", "input", "string"}:
            control = "text"
        else:
            control = "unsupported"
        title = str(raw.get("title") or f"字段 {index + 1}").strip()
        field_id = str(raw.get("id") or raw.get("_id") or "").strip()
        return {
            "key": f"{source}:{field_id or f'{index}:{title}'}",
            "id": field_id,
            "source": source,
            "title": title,
            "description": str(raw.get("desc") or "").strip(),
            "control": control,
            "required": bool(raw.get("required")) or forced_required,
            "options": options,
            "min_select": MiaoyingService._safe_int(raw.get("minSelect"), 1 if raw.get("required") or forced_required else 0),
            "max_select": MiaoyingService._safe_int(raw.get("maxSelect"), len(options) if is_multi and options else 1),
            "max_length": MiaoyingService._safe_int(raw.get("limitCharlt"), 0),
        }

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default

    def _build_submission(
        self,
        account: MiaoyingAccountRow,
        remote_tongji_id: str,
        requirements: dict,
        answers: dict,
        location_name,
        latitude,
        longitude,
    ) -> dict:
        identity = requirements.get("identity") or {}
        selected = answers.get("__identity") or {}
        if not isinstance(selected, dict):
            raise MiaoyingValidationError("签到身份格式无效，请重新选择班级和姓名")
        roster_entry = None
        if identity.get("fixed"):
            matches = [row for row in identity.get("roster", [])
                       if all(str(row.get(key, "")) == str(selected.get(key, ""))
                              for key in ("no", "noLabel", "name", "groupName"))]
            if len(matches) != 1:
                raise MiaoyingValidationError("请选择当前项目的班级和姓名；名单可能已更新，请重新同步并选择")
            roster_entry = matches[0]
        real_name = roster_entry["name"] if roster_entry else account.real_name.strip()
        school_no = roster_entry["noLabel"] if roster_entry else account.school_no.strip()
        class_name = (
            str(roster_entry.get("groupName") or "").strip()
            if roster_entry else account.class_name.strip()
        )
        if not real_name:
            raise MiaoyingValidationError("请先在账号资料中填写签到姓名")
        if not school_no:
            raise MiaoyingValidationError("请先在账号资料中填写数字学号")
        try:
            number = int(roster_entry["no"] if roster_entry else school_no)
        except (ValueError, TypeError) as exc:
            raise MiaoyingValidationError("学号必须为数字") from exc

        info_keys: list[str] = []
        info_vals: list[str] = []
        for field in requirements.get("fields") or []:
            value = self._resolve_answer(field, answers, account)
            self._validate_answer(field, value)
            if self._is_empty_answer(value):
                continue
            info_keys.append(field["title"])
            info_vals.append(self._serialize_field_answer(field, value))

        name_label = identity.get("name_label") or "姓名"
        class_label = identity.get("class_label") or "班级"
        if not info_keys:
            info_keys = [name_label]
            info_vals = [real_name]
        elif name_label not in info_keys:
            info_keys.insert(0, name_label)
            info_vals.insert(0, real_name)
        elif roster_entry:
            info_vals[info_keys.index(name_label)] = real_name

        # 固定名单的班级并不是 infoForms 字段，上游不会从 no/noLabel 自动
        # 展示它，因此显式写入 infoKey/infoVal，确保报名结果能看到班级。
        if class_name:
            if class_label in info_keys:
                info_vals[info_keys.index(class_label)] = class_name
            else:
                info_keys.insert(0, class_label)
                info_vals.insert(0, class_name)

        # openLocationInfo=false 时，秒应原生结果页只公开省、市。将完整
        # 地址和坐标同时作为报名字段提交，保证用户仍能看到本次实际点位。
        if latitude is not None and longitude is not None:
            location_label = "打卡实时位置（详细）"
            location_text = str(location_name or "").strip() or "地图选点"
            location_value = (
                f"{location_text}（{float(latitude):.6f}, "
                f"{float(longitude):.6f}）"
            )
            if location_label in info_keys:
                info_vals[info_keys.index(location_label)] = location_value
            else:
                info_keys.append(location_label)
                info_vals.append(location_value)

        return {
            "userId": account.remote_user_id,
            "tongjiId": remote_tongji_id,
            "infoKey": info_keys,
            "infoVal": info_vals,
            "signUrl": "",
            "locationInfo": {
                "name": str(location_name or "").strip() or "地图选点",
                "longtitude": float(longitude or 0),
                "lattitude": float(latitude or 0),
            },
            "no": number,
            "noLabel": school_no,
        }

    @staticmethod
    def _resolve_answer(field: dict, answers: dict, account: MiaoyingAccountRow):
        for key in (field.get("key"), field.get("id"), field.get("title")):
            if key and key in answers:
                return answers[key]
        title = str(field.get("title") or "").replace(" ", "")
        if "姓名" in title:
            return account.real_name.strip()
        if "学号" in title:
            return account.school_no.strip()
        if "班级" in title:
            return account.class_name.strip()
        return None

    @staticmethod
    def _is_empty_answer(value) -> bool:
        return value is None or value == "" or value == []

    @classmethod
    def _validate_answer(cls, field: dict, value) -> None:
        title = field.get("title") or "未命名字段"
        if field.get("required") and cls._is_empty_answer(value):
            raise MiaoyingValidationError(f"请填写必填项：{title}")
        if cls._is_empty_answer(value):
            return
        values = value if isinstance(value, list) else [value]
        if field.get("control") == "multiple":
            minimum = int(field.get("min_select") or 0)
            maximum = int(field.get("max_select") or 0)
            if len(values) < minimum:
                raise MiaoyingValidationError(f"{title}至少选择 {minimum} 项")
            if maximum and len(values) > maximum:
                raise MiaoyingValidationError(f"{title}最多选择 {maximum} 项")
        allowed = {
            str(candidate)
            for option in field.get("options") or []
            for candidate in (option.get("value"), option.get("label"), option.get("submit_value"))
            if candidate is not None
        }
        if allowed and any(str(item) not in allowed for item in values):
            raise MiaoyingValidationError(f"{title}的选项已发生变化，请重新确认")

    @staticmethod
    def _serialize_answer(value) -> str:
        if isinstance(value, list):
            return "、".join(str(item) for item in value)
        if isinstance(value, (dict, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, bool):
            return "是" if value else "否"
        return str(value)

    @classmethod
    def _serialize_field_answer(cls, field: dict, value) -> str:
        """把界面值转换成秒应实际接收的选项编码。

        前端和旧任务可能保存显示文字，也可能保存 value；这里统一按当前
        项目定义解析，避免项目选项变更时静默提交错误答案。
        """
        options = field.get("options") or []
        if not options:
            return cls._serialize_answer(value)

        lookup: dict[str, str] = {}
        for option in options:
            submit_value = str(option.get("submit_value", option.get("value", "")))
            for candidate in (option.get("value"), option.get("label"), submit_value):
                if candidate is not None:
                    lookup[str(candidate)] = submit_value

        values = value if isinstance(value, list) else [value]
        encoded = [lookup[str(item)] for item in values]
        # 上游 infoVal 的元素本身是字符串；多选在一个元素中以英文逗号
        # 连接选项序号，单选则直接提交单个序号。
        return ",".join(encoded)

    @staticmethod
    def _date_allowed(task, value):
        if task.start_date and value < task.start_date: return False
        if task.end_date and value > task.end_date: return False
        iso=value.isoformat()
        if iso in (task.skip_dates or []): return False
        if task.skip_weekends and value.weekday() >= 5: return False
        return iso in (task.run_dates or []) if task.date_mode == "specific" else True

    def _get_account(self, session, account_id, user):
        row=session.get(MiaoyingAccountRow, account_id)
        if not row or (row.owner_user_id != self._owner(user) and not self._is_admin(user)): raise MiaoyingNotFound("秒应账号不存在")
        return row
    def _get_task(self, session, task_id, user):
        row=session.get(MiaoyingTaskRow, task_id)
        if not row or (row.owner_user_id != self._owner(user) and not self._is_admin(user)): raise MiaoyingNotFound("秒应任务不存在")
        return row
    @staticmethod
    def _account_dict(r): return {"id":r.id,"owner_user_id":r.owner_user_id,"remote_user_id":r.remote_user_id,"nickname":r.nickname,"remark":r.remark,"real_name":r.real_name,"school_no":r.school_no,"class_name":r.class_name,"status":r.status,"enabled":r.enabled,"last_verified_at":r.last_verified_at,"last_sync_at":r.last_sync_at,"last_error":r.last_error,"updated_at":r.updated_at}
    @staticmethod
    def _form_dict(r):
        import re
        remote_times = []
        snapshot = r.raw_snapshot or {}
        for rule in snapshot.get("allowSubmitTimeRules") or []:
            match = re.search(r"(?:T|\s|^)(\d{2}:\d{2}(?::\d{2})?)", str(rule.get("startTime") or ""))
            if match:
                value = match.group(1)
                if len(value) == 5: value += ":00"
                if value not in remote_times: remote_times.append(value)
        requirements = dict(r.requirements or {})
        requirements["location_detail_visible"] = bool(snapshot.get("openLocationInfo"))
        return {"id":r.id,"account_id":r.account_id,"remote_tongji_id":r.remote_tongji_id,"title":r.title,"content":r.content,"is_closed":r.is_closed,"is_repeat":r.is_repeat,"requirements":requirements,"remote_schedule_times":remote_times,"synced_at":r.synced_at}
    @staticmethod
    def _task_dict(r): return {"id":r.id,"owner_user_id":r.owner_user_id,"account_id":r.account_id,"form_id":r.form_id,"name":r.name,"enabled":r.enabled,"schedule_times":r.schedule_times,"start_date":r.start_date,"end_date":r.end_date,"date_mode":r.date_mode,"run_dates":r.run_dates,"skip_dates":r.skip_dates,"skip_weekends":r.skip_weekends,"auto_disable_after_finish":r.auto_disable_after_finish,"location_name":r.location_name,"latitude":float(r.latitude) if r.latitude is not None else None,"longitude":float(r.longitude) if r.longitude is not None else None,"answers":r.answers or {},"answer_schema":r.answer_schema or [],"updated_at":r.updated_at}
    @staticmethod
    def _run_dict(r): return {"id":r.id,"task_id":r.task_id,"account_id":r.account_id,"form_id":r.form_id,"trigger":r.trigger,"status":r.status,"remote_submission_id":r.remote_submission_id,"message":r.message,"started_at":r.started_at,"finished_at":r.finished_at}
