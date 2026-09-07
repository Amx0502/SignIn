import base64
import hashlib
import uuid
from datetime import date, datetime, time, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import config
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
                    MiaoyingQrSessionRow.expires_at > now,
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
        expires_at = datetime.now() + timedelta(minutes=5)
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
            return [self._form_dict(row) for row in session.scalars(select(MiaoyingFormRow).where(MiaoyingFormRow.account_id == account.id).order_by(MiaoyingFormRow.synced_at.desc()))]

    def list_forms(self, account_id: int, user: dict) -> list[dict]:
        with self.database.session() as session:
            account = self._get_account(session, account_id, user)
            return [self._form_dict(row) for row in session.scalars(select(MiaoyingFormRow).where(MiaoyingFormRow.account_id == account.id).order_by(MiaoyingFormRow.synced_at.desc()))]

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
            detail = self.client.get_tongji(token, form.remote_tongji_id)
            requirements = self._requirements(detail)
            if requirements["unsupported"]:
                raise MiaoyingValidationError(
                    "该项目需要当前版本不支持的字段："
                    + "、".join(requirements["unsupported"])
                )
            if detail.get("isClosed"):
                raise MiaoyingValidationError("秒应项目已关闭")
            records = self.client.get_records(token, account.remote_user_id)
            if not detail.get("isRepeat") and any(
                str(item.get("tongjiId")) == form.remote_tongji_id
                for item in records
            ):
                raise MiaoyingValidationError("该账号已提交此签到项目")
            if not account.real_name.strip():
                raise MiaoyingValidationError("请先在账号资料中填写签到姓名")
            if not account.school_no.strip():
                raise MiaoyingValidationError("请先在账号资料中填写数字学号")
            try:
                number = int(account.school_no)
            except ValueError as exc:
                raise MiaoyingValidationError("学号必须为数字") from exc
            latitude = payload.get("latitude")
            longitude = payload.get("longitude")
            if requirements["location"] and (latitude is None or longitude is None):
                raise MiaoyingValidationError("该项目要求位置，请先在地图中选择签到位置")
            submission = {
                "userId": account.remote_user_id,
                "tongjiId": form.remote_tongji_id,
                "infoKey": ["姓名"],
                "infoVal": [account.real_name.strip()],
                "signUrl": "",
                "locationInfo": {
                    "name": str(payload.get("location_name") or "地图选点"),
                    "longtitude": float(longitude or 0),
                    "lattitude": float(latitude or 0),
                },
                "no": number,
                "noLabel": account.school_no,
            }
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
            row = MiaoyingTaskRow(owner_user_id=self._owner(user), **payload)
            session.add(row); session.flush()
            return self._task_dict(row)

    def update_task(self, task_id: int, payload: dict, user: dict) -> dict:
        with self.database.session() as session:
            row = self._get_task(session, task_id, user)
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
            detail = self.client.get_tongji(self._token(account), form.remote_tongji_id)
            requirements = self._requirements(detail)
            blocked = requirements["unsupported"]
            if blocked: raise MiaoyingValidationError("该项目需要当前版本不支持的字段：" + "、".join(blocked))
            if detail.get("isClosed"): raise MiaoyingValidationError("秒应项目已关闭")
            records = self.client.get_records(self._token(account), account.remote_user_id)
            if not detail.get("isRepeat") and any(str(item.get("tongjiId")) == form.remote_tongji_id for item in records):
                raise MiaoyingValidationError("该账号已提交此签到项目")
            if not account.real_name.strip(): raise MiaoyingValidationError("请先在账号资料中填写签到姓名")
            if not account.school_no.strip(): raise MiaoyingValidationError("请先在账号资料中填写数字学号")
            info_keys, info_vals = ["姓名"], [account.real_name.strip()]
            try: number = int(account.school_no)
            except ValueError: raise MiaoyingValidationError("学号必须为数字")
            if requirements["location"] and (task.latitude is None or task.longitude is None):
                raise MiaoyingValidationError("该项目要求位置，请先配置经纬度")
            payload = {"userId": account.remote_user_id, "tongjiId": form.remote_tongji_id, "infoKey": info_keys, "infoVal": info_vals, "signUrl": "", "locationInfo": {"name": task.location_name, "longtitude": float(task.longitude or 0), "lattitude": float(task.latitude or 0)}, "no": number, "noLabel": account.school_no}
            remote_id = self.client.submit(self._token(account), payload)
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

    @staticmethod
    def _requirements(data):
        unsupported=[]
        flags=(("needWifi","Wi-Fi"),("needImages","图片"),("imageIsRequired","图片"),("needVideo","视频"),("videoIsRequired","视频"),("needAudio","录音"),("audioIsRequired","录音"),("needSignature","签名"))
        for key,label in flags:
            if data.get(key) and label not in unsupported: unsupported.append(label)
        for field in data.get("infoForms") or []:
            title = str(field.get("title") or "复杂必填项")
            if field.get("required") and (field.get("type") not in (None,"text","input") or title not in {"姓名", "学号"}):
                label=title
                if label not in unsupported: unsupported.append(label)
        for field in data.get("requiredFields") or []:
            label = str(field.get("title") if isinstance(field, dict) else field)
            if label and label not in {"姓名", "学号"} and label not in unsupported:
                unsupported.append(label)
        return {"location": bool(data.get("needLocation") or data.get("needSubmitLocation")), "unsupported": unsupported}

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
    def _account_dict(r): return {"id":r.id,"owner_user_id":r.owner_user_id,"remote_user_id":r.remote_user_id,"nickname":r.nickname,"remark":r.remark,"real_name":r.real_name,"school_no":r.school_no,"status":r.status,"enabled":r.enabled,"last_verified_at":r.last_verified_at,"last_sync_at":r.last_sync_at,"last_error":r.last_error,"updated_at":r.updated_at}
    @staticmethod
    def _form_dict(r):
        import re
        remote_times = []
        for rule in (r.raw_snapshot or {}).get("allowSubmitTimeRules") or []:
            match = re.search(r"(?:T|\s|^)(\d{2}:\d{2}(?::\d{2})?)", str(rule.get("startTime") or ""))
            if match:
                value = match.group(1)
                if len(value) == 5: value += ":00"
                if value not in remote_times: remote_times.append(value)
        return {"id":r.id,"account_id":r.account_id,"remote_tongji_id":r.remote_tongji_id,"title":r.title,"content":r.content,"is_closed":r.is_closed,"is_repeat":r.is_repeat,"requirements":r.requirements,"remote_schedule_times":remote_times,"synced_at":r.synced_at}
    @staticmethod
    def _task_dict(r): return {"id":r.id,"owner_user_id":r.owner_user_id,"account_id":r.account_id,"form_id":r.form_id,"name":r.name,"enabled":r.enabled,"schedule_times":r.schedule_times,"start_date":r.start_date,"end_date":r.end_date,"date_mode":r.date_mode,"run_dates":r.run_dates,"skip_dates":r.skip_dates,"skip_weekends":r.skip_weekends,"auto_disable_after_finish":r.auto_disable_after_finish,"location_name":r.location_name,"latitude":float(r.latitude) if r.latitude is not None else None,"longitude":float(r.longitude) if r.longitude is not None else None,"updated_at":r.updated_at}
    @staticmethod
    def _run_dict(r): return {"id":r.id,"task_id":r.task_id,"account_id":r.account_id,"form_id":r.form_id,"trigger":r.trigger,"status":r.status,"remote_submission_id":r.remote_submission_id,"message":r.message,"started_at":r.started_at,"finished_at":r.finished_at}
