from datetime import datetime

import requests

from .class_cube_settings import validate_wecom_webhook


class MiaoyingNotificationError(RuntimeError):
    pass


class MiaoyingNotifier:
    TRIGGER_NAMES = {
        "manual": "手动立即执行",
        "scheduler": "定时自动执行",
    }

    def send(
        self,
        webhook_url: str,
        *,
        account_name: str,
        form_name: str,
        status: str,
        message: str,
        trigger: str,
        latitude=None,
        longitude=None,
    ) -> None:
        url = validate_wecom_webhook(webhook_url)
        if not url:
            return
        now = datetime.now()
        success = status == "success"
        result = "签到成功" if success else (message or "签到失败")
        icon = "✅" if success else "❌"
        detail_lines = [f"- {icon} {account_name or '-'} [{now.strftime('%H:%M:%S')}]"]
        if latitude is not None and longitude is not None:
            detail_lines.append(
                f"  （📍位置：{float(longitude):.6f}, {float(latitude):.6f}）"
            )
        detail_lines.append(f"  （类型：秒应签到；结果：{result}）")
        content = (
            "## 📊 秒应通知汇总\n\n"
            f"时间：{now.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"项目：{form_name or '-'}\n\n"
            f"触发：{self.TRIGGER_NAMES.get(trigger, '自动任务')}\n\n"
            f"成功：{1 if success else 0} 个｜失败：{0 if success else 1} 个\n\n"
            + "\n".join(detail_lines)
        )
        try:
            response = requests.post(
                url,
                json={"msgtype": "markdown", "markdown": {"content": content}},
                timeout=10,
                allow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise MiaoyingNotificationError("企业微信通知发送失败") from exc
        if not isinstance(payload, dict) or payload.get("errcode") != 0:
            raise MiaoyingNotificationError("企业微信通知发送失败")

    def send_test(self, webhook_url: str) -> None:
        url = validate_wecom_webhook(webhook_url)
        if not url:
            raise MiaoyingNotificationError("请先填写企业微信机器人 Webhook")
        content = (
            "## ✅ 秒应机器人连接测试\n\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "状态：配置有效，签到通知可以正常发送"
        )
        try:
            response = requests.post(
                url,
                json={"msgtype": "markdown", "markdown": {"content": content}},
                timeout=10,
                allow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise MiaoyingNotificationError("企业微信测试通知发送失败") from exc
        if not isinstance(payload, dict) or payload.get("errcode") != 0:
            detail = str(payload.get("errmsg") or "企业微信拒绝了该 Webhook") if isinstance(payload, dict) else "企业微信返回异常"
            raise MiaoyingNotificationError(f"企业微信测试通知发送失败：{detail}")
