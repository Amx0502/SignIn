import base64
import datetime as dt
import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import requests
import rsa

from .config import (
    DATA_FILE,
    DEFAULT_REFRESH_TIMES,
    DEFAULT_WEBHOOK_URL,
    HEADERS,
    LOG_DIR,
    PUBLIC_KEY,
    SETTINGS_FILE,
)


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")


def deep_copy(data):
    return json.loads(json.dumps(data, ensure_ascii=False))


def normalize_time_text(text: str) -> str:
    text = str(text).strip()
    if not text:
        raise ValueError("时间不能为空")
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"时间格式无效: {text}，请使用 HH:MM 或 HH:MM:SS")


def parse_time_list(value) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").replace("，", ",").split(",")

    results: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        results.append(normalize_time_text(text))
    return list(dict.fromkeys(results))


def normalize_task(task: dict | None = None) -> dict:
    task = task or {}
    raw_pic = task.get("pic_path", [])
    if isinstance(raw_pic, str):
        pic_paths = [raw_pic.strip()] if raw_pic.strip() else []
    elif isinstance(raw_pic, list):
        pic_paths = [str(p).strip() for p in raw_pic if str(p).strip()]
    else:
        pic_paths = []
    mode = str(task.get("mode", "")).strip() or ("image" if pic_paths else "normal")
    if mode not in {"normal", "image"}:
        mode = "normal"
    return {
        "index": int(task.get("index", 1) or 1),
        "title": str(task.get("title", "")).strip() or f"任务{task.get('index', 1)}",
        "times": parse_time_list(task.get("times", [])),
        "enable": bool(task.get("enable", True)),
        "use_location": bool(task.get("use_location", False)),
        "text": str(task.get("text", "")),
        "pic_path": pic_paths,
        "skip_weekends": bool(task.get("skip_weekends", False)),
        "mode": mode,
    }


def normalize_account(account: dict | None = None) -> dict:
    account = account or {}
    return {
        "name": str(account.get("name", "")).strip(),
        "mobile": str(account.get("mobile", "")).strip(),
        "password": str(account.get("password", "")),
        "token": str(account.get("token", "")).strip(),
        "tasks": [normalize_task(item) for item in account.get("tasks", [])],
    }


def load_accounts_from_disk() -> list[dict]:
    ensure_dirs()
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("accounts.json 必须是数组格式")
    return [normalize_account(item) for item in data]


def save_accounts_to_disk(accounts: list[dict]) -> None:
    ensure_dirs()
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(accounts, file, ensure_ascii=False, indent=2)


def load_settings_from_disk() -> dict:
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        return {
            "auto_enabled": True,
            "refresh_times": DEFAULT_REFRESH_TIMES.copy(),
            "webhook_url": DEFAULT_WEBHOOK_URL,
        }
    with SETTINGS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("settings.json 必须是对象格式")
    return {
        "auto_enabled": bool(data.get("auto_enabled", True)),
        "refresh_times": parse_time_list(data.get("refresh_times", DEFAULT_REFRESH_TIMES)),
        "webhook_url": str(data.get("webhook_url", DEFAULT_WEBHOOK_URL)),
    }


def save_settings_to_disk(auto_enabled: bool, refresh_times: list[str], webhook_url: str = "") -> None:
    ensure_dirs()
    with SETTINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "auto_enabled": auto_enabled,
                "refresh_times": refresh_times,
                "webhook_url": webhook_url,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )


class MemoryLogHandler(logging.Handler):
    def __init__(self, buffer: deque[str]) -> None:
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(self.format(record))
        except Exception:
            pass


def setup_logger(log_buffer: deque[str]) -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("sign_in_web")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = TimedRotatingFileHandler(
        filename=str(LOG_DIR / "checkin.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    memory_handler = MemoryLogHandler(log_buffer)
    memory_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(memory_handler)
    return logger


class CheckinService:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    @staticmethod
    def encrypt_pwd(password: str) -> str:
        pub_key = rsa.PublicKey.load_pkcs1_openssl_pem(PUBLIC_KEY.encode())
        encrypted = rsa.encrypt(password.encode(), pub_key)
        return base64.b64encode(encrypted).decode()

    def login(self, mobile: str, password: str) -> str | None:
        encrypted_pwd = self.encrypt_pwd(password)
        url = "https://api-xcx-qunsou.weiyoubot.cn/xcx/checkin/v2/user/mobile/login"
        response = requests.post(
            url,
            json={"mobile": mobile, "pwd": encrypted_pwd},
            headers=HEADERS,
            timeout=15,
        ).json()
        if response.get("msg") == "ok":
            return response["data"]["access_token"]
        return None

    def fetch_checkin_list(self, token: str) -> list[dict]:
        url = (
            "https://api-xcx-qunsou.weiyoubot.cn/xcx/checkin/v3/list"
            f"?type=5&page=1&count=100&access_token={token}"
        )
        response = requests.get(url, headers=HEADERS, timeout=15).json()
        return response.get("data", []) or []

    def fetch_detail(self, cid: str, token: str) -> dict:
        url = (
            "https://api-xcx-qunsou.weiyoubot.cn/xcx/checkin/v4/detail"
            f"?cid={cid}&access_token={token}&tag=0"
        )
        return requests.get(url, headers=HEADERS, timeout=15).json()

    def upload_image(self, image_path: str, token: str) -> str | None:
        path = Path(image_path)
        if not path.is_absolute():
            path = DATA_FILE.parent / path
        if not path.exists():
            return None

        upload_headers = dict(HEADERS)
        upload_headers.pop("Content-Type", None)
        url = f"https://api-xcx-qunsou.weiyoubot.cn/xcx/file/v1/upload?access_token={token}"
        with path.open("rb") as image_file:
            files = {"file": (path.name, image_file, "image/jpeg")}
            response = requests.post(url, headers=upload_headers, files=files, timeout=20).json()

        if response.get("sta") == 0 and response.get("data", {}).get("urls"):
            return response["data"]["urls"][0]

        return None

    def build_payload(self, token: str, cid: str, task: dict, detail: dict | None, image_urls: list[str] | None = None) -> dict:
        payload = {
            "cid": cid,
            "text": str(task.get("text", "")),
            "access_token": token,
            "fill_params": [{"key": 1, "val": str(task.get("text", ""))}],
        }

        image_urls = image_urls or []
        if image_urls:
            payload["fill_params"].append({"key": 2, "val": image_urls})

        if task.get("use_location"):
            locations = (detail or {}).get("data", {}).get("locations") or []
            if locations:
                location = locations[0]
                payload["wifi_location_info"] = {
                    "latitude": float(location["latitude"]),
                    "longitude": float(location["longitude"]),
                    "accuracy": 323,
                    "wifi": "",
                }
                payload["fill_params"].append({
                    "key": 6,
                    "val": location.get("address", ""),
                    "lat": round(float(location["latitude"]), 5),
                    "lon": round(float(location["longitude"]), 5),
                })
                payload["wifi_match"] = 0
        return payload

    def execute_task(self, account: dict, task: dict) -> tuple[bool, dict]:
        name = account["name"] or account["mobile"]
        task_title = task.get("title", "未命名任务")

        token = account.get("token", "").strip()
        if not token:
            return False, {"error": f"[{name}] 任务《{task_title}》Token 为空，请先登录或刷新 Token"}

        checkin_list = self.fetch_checkin_list(token)
        if not checkin_list:
            return False, {"error": f"[{name}] 任务《{task_title}》无可用签到项目，Token 可能已失效"}

        target_index = int(task.get("index", 1)) - 1
        if target_index < 0 or target_index >= len(checkin_list):
            return False, {"error": f"[{name}] 任务《{task_title}》指定的序号不存在"}

        target_item = checkin_list[target_index]
        cid = target_item["cid"]
        real_title = target_item.get("title", "未知项目")

        detail = None
        if task.get("use_location"):
            detail = self.fetch_detail(cid, token)

        pic_paths = task.get("pic_path", []) or []
        image_urls = []
        if pic_paths:
            for idx, pic_path in enumerate(pic_paths, start=1):
                image_url = self.upload_image(str(pic_path), token)
                if not image_url:
                    return False, {"error": f"[{name}] 任务《{task_title}》第 {idx} 张图片上传失败"}
                image_urls.append(image_url)
                if idx < len(pic_paths):
                    time.sleep(6.5)

        payload = self.build_payload(token, cid, task, detail, image_urls)
        response = requests.post(
            "https://api-xcx-qunsou.weiyoubot.cn/xcx/checkin/v3/doit",
            headers=HEADERS,
            json=payload,
            timeout=20,
        ).json()

        if response.get("msg") == "ok" or response.get("sta") == 0:
            result = {
                "title": task_title,
                "real_title": real_title,
            }
            text = task.get("text", "").strip()
            if text:
                result["text"] = text
            if image_urls:
                result["image_urls"] = image_urls
            if task.get("use_location"):
                locations = (detail or {}).get("data", {}).get("locations") or []
                if locations:
                    location = locations[0]
                    result["location"] = {
                        "address": location.get("address", ""),
                        "latitude": float(location.get("latitude", 0)),
                        "longitude": float(location.get("longitude", 0)),
                    }
            return True, result

        return False, {"error": f"[{name}] 任务《{task_title}》签到失败：{response.get('msg', '未知错误')}"}

    def send_wechat_notification(self, webhook_url: str, account_name: str, result: dict, success: bool = True) -> None:
        if not webhook_url.strip():
            self.logger.debug("企业微信通知：webhook_url 为空，跳过发送")
            return

        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if success:
            detail_parts = []
            detail_parts.append(f"**{result.get('real_title', '')}**")
            
            if result.get("location"):
                detail_parts.append(f"📍 位置: {result['location'].get('address', '')}")
            
            if result.get("text"):
                detail_parts.append(f"📝 文本: {result['text']}")
            
            if result.get("image_urls") and len(result["image_urls"]):
                detail_parts.append(f"🖼️ 图片: {len(result['image_urls'])}张")
            
            detail_str = " | ".join(detail_parts)
            
            markdown_content = (
                f"**📝 定时签到结果报告**\n\n"
                f"> 执行时间：{now}\n"
                f"> 触发项目目数：1个\n\n"
                f"**执行详情：**\n"
                f"- ✅ {account_name} -> 【{result.get('title', '')}】（实际项目：{detail_str}）\n\n"
                f"日志已同步至服务器"
            )
        else:
            error_msg = result.get("error", "未知错误")
            markdown_content = (
                f"**❌ 定时签到结果报告**\n\n"
                f"> 执行时间：{now}\n"
                f"> 触发项目目数：1个\n\n"
                f"**执行详情：**\n"
                f"- ❌ {account_name} -> 签到失败\n"
                f"错误原因：{error_msg}\n\n"
                f"日志已同步至服务器"
            )
        
        self.logger.info("企业微信通知：开始发送通知，success=%s，account=%s，webhook=%s", 
                         success, account_name, webhook_url[:30] + "..." if len(webhook_url) > 30 else webhook_url)
        self.logger.debug("企业微信通知：markdown内容长度=%d", len(markdown_content))
        
        try:
            response = requests.post(
                webhook_url,
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "content": markdown_content
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            self.logger.debug("企业微信通知：HTTP状态码=%d，响应内容=%s", response.status_code, response.text[:200])
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get("errcode") == 0:
                    self.logger.info("企业微信通知：发送成功，errcode=%d，errmsg=%s", 
                                     resp_json.get("errcode"), resp_json.get("errmsg"))
                else:
                    self.logger.error("企业微信通知：发送失败，errcode=%d，errmsg=%s", 
                                      resp_json.get("errcode"), resp_json.get("errmsg"))
            else:
                self.logger.error("企业微信通知：HTTP请求失败，状态码=%d", response.status_code)
        except requests.exceptions.Timeout:
            self.logger.error("企业微信通知：请求超时（10秒）")
        except requests.exceptions.ConnectionError as exc:
            self.logger.error("企业微信通知：网络连接失败，错误=%s", str(exc))
        except requests.exceptions.RequestException as exc:
            self.logger.error("企业微信通知：请求异常，错误=%s", str(exc))
        except Exception as exc:
            self.logger.error("企业微信通知：未知异常，错误=%s", str(exc))


class AppState:
    def __init__(self) -> None:
        self.log_buffer: deque[str] = deque(maxlen=600)
        self.logger = setup_logger(self.log_buffer)
        self.service = CheckinService(self.logger)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.stop_event = threading.Event()
        self.accounts = load_accounts_from_disk()
        settings = load_settings_from_disk()
        self.auto_enabled = settings["auto_enabled"]
        self.refresh_times = settings["refresh_times"]
        self.webhook_url = settings.get("webhook_url", "")
        if not SETTINGS_FILE.exists():
            save_settings_to_disk(self.auto_enabled, self.refresh_times, self.webhook_url)
        self.run_records: dict[str, str] = {}
        self.token_refresh_records: dict[str, str] = {}
        self.scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("签到 Web 管理系统已启动")

    def shutdown(self) -> None:
        self.stop_event.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.logger.info("系统已停止")

    def snapshot(self) -> dict:
        with self.lock:
            accounts = deep_copy(self.accounts)
            enabled_task_count = sum(
                1 for account in self.accounts for task in account.get("tasks", []) if task.get("enable", True)
            )
            return {
                "accounts": accounts,
                "auto_enabled": self.auto_enabled,
                "refresh_times": self.refresh_times.copy(),
                "webhook_url": self.webhook_url,
                "account_count": len(self.accounts),
                "task_count": sum(len(account.get("tasks", [])) for account in self.accounts),
                "enabled_task_count": enabled_task_count,
                "server_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def get_logs(self, limit: int = 200) -> list[str]:
        with self.lock:
            return list(self.log_buffer)[-limit:]

    def save(self) -> None:
        with self.lock:
            save_accounts_to_disk(self.accounts)

    def set_settings(self, data: dict) -> dict:
        with self.lock:
            if "refresh_times" in data:
                self.refresh_times = parse_time_list(data.get("refresh_times", []))
            if "auto_enabled" in data:
                self.auto_enabled = bool(data["auto_enabled"])
            if "webhook_url" in data:
                self.webhook_url = str(data.get("webhook_url", ""))
            save_settings_to_disk(self.auto_enabled, self.refresh_times, self.webhook_url)
        self.logger.info(
            "系统设置已更新：自动调度=%s，刷新时间=%s",
            "开启" if self.auto_enabled else "关闭",
            ", ".join(self.refresh_times),
        )
        return self.snapshot()

    def add_account(self, data: dict) -> dict:
        account = normalize_account(data)
        if not account["name"] or not account["mobile"] or not account["password"]:
            raise ValueError("账号名称、手机号、密码不能为空")
        with self.lock:
            self.accounts.append(account)
            save_accounts_to_disk(self.accounts)
        self.logger.info("已新增账号：%s", account["name"])
        return account

    def update_account(self, account_index: int, data: dict) -> dict:
        account = normalize_account(data)
        if not account["name"] or not account["mobile"] or not account["password"]:
            raise ValueError("账号名称、手机号、密码不能为空")
        with self.lock:
            account["tasks"] = self.accounts[account_index].get("tasks", [])
            self.accounts[account_index] = account
            save_accounts_to_disk(self.accounts)
        self.logger.info("已更新账号：%s", account["name"])
        return account

    def delete_account(self, account_index: int) -> None:
        with self.lock:
            account = self.accounts.pop(account_index)
            save_accounts_to_disk(self.accounts)
        self.logger.info("已删除账号：%s", account["name"])

    def login_account(self, account_index: int) -> dict:
        with self.lock:
            account = deep_copy(self.accounts[account_index])
        token = self.service.login(account["mobile"], account["password"])
        if not token:
            raise RuntimeError("登录失败，请检查账号信息")
        with self.lock:
            self.accounts[account_index]["token"] = token
            save_accounts_to_disk(self.accounts)
            updated = deep_copy(self.accounts[account_index])
        self.logger.info("[%s] 登录成功并获取 Token", updated["name"])
        return updated

    def refresh_single_token(self, account_index: int) -> dict:
        return self.login_account(account_index)

    def refresh_all_tokens(self) -> dict:
        with self.lock:
            accounts = deep_copy(self.accounts)
        success = 0
        failed_names: list[str] = []
        for index, account in enumerate(accounts):
            token = self.service.login(account["mobile"], account["password"])
            if token:
                accounts[index]["token"] = token
                success += 1
            else:
                failed_names.append(account["name"])
        with self.lock:
            self.accounts = accounts
            save_accounts_to_disk(self.accounts)
        if failed_names:
            self.logger.warning("批量刷新 Token 完成，成功 %s 个，失败 %s 个：%s", success, len(failed_names), "、".join(failed_names))
        else:
            self.logger.info("批量刷新 Token 完成，成功 %s 个账号", success)
        return {"success_count": success}

    def _refresh_single_token(self, mobile: str, password: str) -> None:
        token = self.service.login(mobile, password)
        if token:
            with self.lock:
                for account in self.accounts:
                    if account["mobile"] == mobile:
                        account["token"] = token
                        break
                save_accounts_to_disk(self.accounts)
            self.logger.info("用户[%s] Token 刷新成功", mobile)
        else:
            self.logger.warning("用户[%s] Token 刷新失败", mobile)

    def fetch_projects(self, account_index: int) -> list[dict]:
        with self.lock:
            account = deep_copy(self.accounts[account_index])
        if not account.get("token"):
            raise ValueError("当前账号没有 Token，请先登录")
        projects = self.service.fetch_checkin_list(account["token"])
        self.logger.info("[%s] 已获取签到项目列表，共 %s 个", account["name"], len(projects))
        return projects

    def add_task(self, account_index: int, data: dict) -> dict:
        task = normalize_task(data)
        with self.lock:
            self.accounts[account_index].setdefault("tasks", []).append(task)
            save_accounts_to_disk(self.accounts)
        self.logger.info("[%s] 已新增任务：%s", self.accounts[account_index]["name"], task["title"])
        return task

    def update_task(self, account_index: int, task_index: int, data: dict) -> dict:
        task = normalize_task(data)
        with self.lock:
            self.accounts[account_index]["tasks"][task_index] = task
            save_accounts_to_disk(self.accounts)
            account_name = self.accounts[account_index]["name"]
        self.logger.info("[%s] 已更新任务：%s", account_name, task["title"])
        return task

    def delete_task(self, account_index: int, task_index: int) -> None:
        with self.lock:
            task = self.accounts[account_index]["tasks"].pop(task_index)
            account_name = self.accounts[account_index]["name"]
            save_accounts_to_disk(self.accounts)
        self.logger.info("[%s] 已删除任务：%s", account_name, task["title"])

    def enqueue_task(self, account: dict, task: dict) -> None:
        self.executor.submit(self._execute_task, normalize_account(account), normalize_task(task))

    def run_task(self, account_index: int, task_index: int) -> dict:
        with self.lock:
            account = deep_copy(self.accounts[account_index])
            task = deep_copy(self.accounts[account_index]["tasks"][task_index])
            webhook_url = self.webhook_url
        ok, result = self.service.execute_task(account, task)
        name = account.get("name") or account.get("mobile")
        if ok:
            real_title = result.get("real_title", "未知项目")
            message = f"[{name}] 任务《{result['title']}》签到成功，实际项目：{real_title}"
            if result.get("text"):
                message += f"，文本：{result['text']}"
            if result.get("image_urls"):
                message += f"，图片数量：{len(result['image_urls'])}"
            if result.get("location"):
                message += f"，位置：{result['location'].get('address', '')}"
            self.logger.info(message)
            try:
                self.service.send_wechat_notification(webhook_url, name, result, success=True)
            except Exception:
                pass
            return result
        else:
            error_msg = result.get("error", "签到失败")
            self.logger.error(error_msg)
            try:
                self.service.send_wechat_notification(webhook_url, name, result, success=False)
            except Exception:
                pass
            raise RuntimeError(error_msg)

    def run_account_tasks(self, account_index: int) -> dict:
        with self.lock:
            account = deep_copy(self.accounts[account_index])
        tasks = [task for task in account.get("tasks", []) if task.get("enable", True)]
        for task in tasks:
            self.enqueue_task(account, task)
        return {"queued_count": len(tasks)}

    def run_all_enabled_tasks(self) -> dict:
        queued_count = 0
        with self.lock:
            accounts = deep_copy(self.accounts)
        for account in accounts:
            for task in account.get("tasks", []):
                if task.get("enable", True):
                    self.enqueue_task(account, task)
                    queued_count += 1
        return {"queued_count": queued_count}

    def _execute_task(self, account: dict, task: dict) -> None:
        try:
            ok, result = self.service.execute_task(account, task)
            name = account.get("name") or account.get("mobile")
            task_title = task.get("title", "未命名任务")
            if ok:
                real_title = result.get("real_title", "未知项目")
                message = f"[{name}] 任务《{task_title}》签到成功，实际项目：{real_title}"
                if result.get("text"):
                    message += f"，文本：{result['text']}"
                if result.get("image_urls"):
                    message += f"，图片数量：{len(result['image_urls'])}"
                if result.get("location"):
                    message += f"，位置：{result['location'].get('address', '')}"
                self.logger.info(message)
                try:
                    with self.lock:
                        webhook_url = self.webhook_url
                    self.service.send_wechat_notification(webhook_url, name, result, success=True)
                except Exception:
                    pass
            else:
                error_msg = result.get("error", f"[{name}] 任务《{task_title}》签到失败")
                self.logger.error(error_msg)
                try:
                    with self.lock:
                        webhook_url = self.webhook_url
                    self.service.send_wechat_notification(webhook_url, name, result, success=False)
                except Exception:
                    pass
        except Exception as exc:
            self.logger.error("[%s] 执行任务异常：%s", account.get("name") or account.get("mobile"), exc)

    def scheduler_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.process_schedule()
            except Exception as exc:
                self.logger.error("自动调度异常：%s", exc)
            time.sleep(1)

    @staticmethod
    def _time_reached(now: dt.datetime, target_time: str) -> bool:
        hour, minute, second = map(int, target_time.split(":"))
        target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return now >= target

    def process_schedule(self) -> None:
        now = dt.datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        weekday = now.weekday()

        with self.lock:
            auto_enabled = self.auto_enabled
            refresh_times = self.refresh_times.copy()
            accounts = deep_copy(self.accounts)
        if not auto_enabled:
            return

        for account in accounts:
            mobile = account.get("mobile")
            for task in account.get("tasks", []):
                if not task.get("enable", True):
                    continue
                if task.get("skip_weekends", False) and weekday in (5, 6):
                    continue
                for target_time in task.get("times", []):
                    hour, minute, second = map(int, target_time.split(":"))
                    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
                    time_diff = abs((now - target).total_seconds())
                    
                    refresh_target = target - dt.timedelta(minutes=30)
                    refresh_time_diff = abs((now - refresh_target).total_seconds())
                    
                    if refresh_time_diff <= 300:
                        refresh_record_key = f"{mobile}_{target_time}_refresh"
                        should_refresh = False
                        with self.lock:
                            if self.token_refresh_records.get(refresh_record_key) != current_date:
                                self.token_refresh_records[refresh_record_key] = current_date
                                should_refresh = True
                        if should_refresh:
                            self.logger.info("为用户[%s]在任务时间[%s]前30分钟刷新Token", mobile, target_time)
                            self.executor.submit(self._refresh_single_token, mobile, account["password"])
                    
                    if time_diff <= 300:
                        record_key = f"{mobile}_{task.get('title')}_{target_time}"
                        should_run = False
                        with self.lock:
                            if self.run_records.get(record_key) != current_date:
                                self.run_records[record_key] = current_date
                                should_run = True
                        if should_run:
                            self.enqueue_task(account, task)
