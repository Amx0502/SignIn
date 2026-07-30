from datetime import datetime
import math

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
    STATUS_ICONS = {
        "success": "✅",
        "already_signed": "✅",
        "waiting_parameter": "⏭️",
        "skipped": "⏭️",
        "no_sign_in": "ℹ️",
        "unknown_result": "❌",
        "failed": "❌",
    }

    def __init__(self, http=None):
        self.http = http or requests

    @staticmethod
    def _time_text(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        text = str(value or datetime.now().strftime("%Y-%m-%d %H:%M"))
        return text[:16]

    @staticmethod
    def _detail_time(detail: dict, summary: dict) -> str:
        value = detail.get("executed_at") or summary.get("started_at")
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        text = str(value or datetime.now().strftime("%H:%M:%S"))
        return text[-8:] if len(text) >= 8 else text

    @staticmethod
    def _coordinate_text(value) -> str | None:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number):
            return None
        return f"{number:.2f}"

    @staticmethod
    def _parameter_lines(parameters: dict) -> list[str]:
        lines = []
        longitude = ClassCubeNotifier._coordinate_text(
            parameters.get("longitude")
        )
        latitude = ClassCubeNotifier._coordinate_text(
            parameters.get("latitude")
        )
        if longitude is not None and latitude is not None:
            lines.append(f"（📍位置：{longitude}, {latitude}）")
        image_count = int(parameters.get("image_count") or 0)
        if image_count > 0:
            lines.append(f"（🖼️图片：{image_count}张）")
        password = parameters.get("password")
        if password not in (None, ""):
            lines.append(f"（🔑密码：{password}）")
        return lines

    def send_summary(self, webhook_url: str, summary: dict) -> None:
        url = validate_wecom_webhook(webhook_url)
        if not url:
            return
        parameters = summary.get("parameters") or {}
        parameter_lines = self._parameter_lines(parameters)
        detail_lines = []
        for detail in summary.get("details", []):
            if isinstance(detail, dict):
                mode = self.MODE_NAMES.get(
                    str(detail.get("mode") or ""),
                    "未知类型",
                )
                status = self.STATUS_NAMES.get(
                    str(detail.get("status") or ""),
                    str(detail.get("message") or "执行完成"),
                )
                icon = self.STATUS_ICONS.get(
                    str(detail.get("status") or ""),
                    "ℹ️",
                )
                executed_at = self._detail_time(detail, summary)
                account_name = summary.get("account_name", "-")
                detail_lines.append(
                    f"- {icon} {account_name} [{executed_at}]"
                )
                detail_lines.extend(
                    f"  {line}" for line in parameter_lines
                )
                detail_lines.append(
                    f"  （类型：{mode}；结果：{status}）"
                )
            else:
                detail_lines.append(f"- {detail}")
        details = "\n".join(detail_lines)
        trigger = self.TRIGGER_NAMES.get(
            str(summary.get("trigger") or ""),
            "自动任务",
        )
        success_count = int(summary.get("success", 0) or 0) + int(
            summary.get("already_signed", 0) or 0
        )
        failed_count = int(summary.get("failed", 0) or 0) + int(
            summary.get("unknown", 0) or 0
        )
        content = (
            "## 📊 班级魔方通知汇总\n\n"
            f"时间：{self._time_text(summary.get('started_at'))}\n\n"
            f"课程：{summary.get('course_name', '-')}\n\n"
            f"触发：{trigger}\n\n"
            f"成功：{success_count} 个｜失败：{failed_count} 个"
        )
        if details:
            content = f"{content}\n\n{details}"
        elif parameter_lines:
            content = (
                f"{content}\n\n任务参数：\n"
                + "\n".join(parameter_lines)
            )
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
