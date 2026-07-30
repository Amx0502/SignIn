import requests

from .class_cube_settings import validate_wecom_webhook


class ClassCubeNotificationError(RuntimeError):
    pass


class ClassCubeNotifier:
    def __init__(self, http=None):
        self.http = http or requests

    def send_summary(self, webhook_url: str, summary: dict) -> None:
        url = validate_wecom_webhook(webhook_url)
        if not url:
            return
        detail_lines = []
        for detail in summary.get("details", []):
            if isinstance(detail, dict):
                title = detail.get("title") or "签到项"
                message = detail.get("message") or detail.get("status") or "-"
                detail_lines.append(f"{title}：{message}")
            else:
                detail_lines.append(str(detail))
        details = "\n".join(f"> {line}" for line in detail_lines)
        content = (
            f"### 班级魔方签到结果\n"
            f"- 任务：{summary.get('task_name', '-')}\n"
            f"- 账号：{summary.get('account_name', '-')}\n"
            f"- 课程：{summary.get('course_name', '-')}\n"
            f"- 成功：{summary.get('success', 0)}，失败："
            f"{summary.get('failed', 0)}"
        )
        if details:
            content = f"{content}\n{details}"
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
