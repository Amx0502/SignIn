from datetime import datetime

import requests

from .class_cube_settings import validate_wecom_webhook


class MiaoyingNotificationError(RuntimeError):
    pass


class MiaoyingNotifier:
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
        result = "✅ 签到成功" if status == "success" else f"❌ {message or '签到失败'}"
        lines = [
            "## 📊 秒应签到通知",
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"账号：{account_name or '-'}",
            f"项目：{form_name or '-'}",
            f"触发：{'手动执行' if trigger == 'manual' else '定时自动执行'}",
            f"结果：{result}",
        ]
        if latitude is not None and longitude is not None:
            lines.append(f"位置：{float(latitude):.6f}, {float(longitude):.6f}")
        try:
            response = requests.post(
                url,
                json={"msgtype": "markdown", "markdown": {"content": "\n\n".join(lines)}},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise MiaoyingNotificationError("企业微信通知发送失败") from exc
        if not isinstance(payload, dict) or payload.get("errcode") != 0:
            raise MiaoyingNotificationError("企业微信通知发送失败")
