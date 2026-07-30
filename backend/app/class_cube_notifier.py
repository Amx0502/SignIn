from datetime import datetime

import requests

from .class_cube_settings import validate_wecom_webhook


class ClassCubeNotificationError(RuntimeError):
    pass


class ClassCubeNotifier:
    TRIGGER_NAMES = {
        "manual": "手动立即执行",
        "scheduled": "定时自动执行",
    }
    MODE_NAMES = {
        "qr": "二维码签到",
        "gps": "GPS 签到",
        "gps_photo": "GPS+拍照签到",
        "password": "密码签到",
        "task": "任务检查",
    }
    STATUS_NAMES = {
        "success": "签到成功",
        "already_signed": "已完成，无需重复签到",
        "waiting_parameter": "缺少签到参数",
        "unknown_result": "结果待人工确认",
        "skipped": "无需提交",
        "no_sign_in": "当前没有签到项",
        "failed": "签到失败",
    }

    def __init__(self, http=None):
        self.http = http or requests

    @staticmethod
    def _time_text(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @classmethod
    def _title(cls, summary: dict) -> str:
        status = str(summary.get("status") or "")
        if status == "success":
            return "✅ 班级魔方签到成功"
        if status in {"already_signed", "skipped", "no_sign_in"}:
            return "ℹ️ 班级魔方签到检查完成"
        if status == "unknown_result":
            return "⚠️ 班级魔方签到结果待确认"
        return "❌ 班级魔方签到执行异常"

    def send_summary(self, webhook_url: str, summary: dict) -> None:
        url = validate_wecom_webhook(webhook_url)
        if not url:
            return
        detail_lines = []
        for detail in summary.get("details", []):
            if isinstance(detail, dict):
                title = detail.get("title") or "签到项"
                mode = self.MODE_NAMES.get(
                    str(detail.get("mode") or ""),
                    "未知类型",
                )
                status = self.STATUS_NAMES.get(
                    str(detail.get("status") or ""),
                    str(detail.get("message") or "执行完成"),
                )
                detail_lines.append(
                    f"- **{title}**｜{mode}｜{status}"
                )
            else:
                detail_lines.append(f"- {detail}")
        details = "\n".join(detail_lines)
        trigger = self.TRIGGER_NAMES.get(
            str(summary.get("trigger") or ""),
            "自动任务",
        )
        content = (
            f"## {self._title(summary)}\n\n"
            f"**执行时间**：{self._time_text(summary.get('started_at'))}\n\n"
            f"**触发方式**：{trigger}\n\n"
            f"**任务**：{summary.get('task_name', '-')}\n\n"
            f"**账号**：{summary.get('account_name', '-')}\n\n"
            f"**课程**：{summary.get('course_name', '-')}\n\n"
            f"**执行汇总**：扫描 {summary.get('scanned', 0)} 项｜"
            f"成功 {summary.get('success', 0)} 项｜"
            f"已完成 {summary.get('already_signed', 0)} 项｜"
            f"跳过 {summary.get('skipped', 0)} 项｜"
            f"失败 {summary.get('failed', 0)} 项｜"
            f"待确认 {summary.get('unknown', 0)} 项"
        )
        if details:
            content = f"{content}\n\n### 签到明细\n{details}"
        try:
            response = self.http.post(
                url,
                json={
                    "msgtype": "markdown",
                    "markdown": {"content": content},
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ClassCubeNotificationError(
                "企业微信通知发送失败"
            ) from exc
        if not isinstance(payload, dict) or payload.get("errcode") != 0:
            raise ClassCubeNotificationError("企业微信通知发送失败")
