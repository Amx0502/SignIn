from datetime import date, datetime


def normalize_schedule_times(values) -> list[str]:
    normalized = set()
    for value in values or []:
        text = str(value).strip()
        try:
            parsed = datetime.strptime(text, "%H:%M:%S")
        except ValueError as exc:
            raise ValueError("执行时间必须使用 HH:mm:ss 格式") from exc
        normalized.add(parsed.strftime("%H:%M:%S"))
    return sorted(normalized)


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def due_schedule_key(
    task: dict,
    now: datetime,
    grace_seconds: int = 59,
) -> str | None:
    today = now.date()
    start = _as_date(task.get("start_date"))
    end = _as_date(task.get("end_date"))
    if (start and today < start) or (end and today > end):
        return None
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    for value in normalize_schedule_times(task.get("schedule_times", [])):
        scheduled = datetime.strptime(value, "%H:%M:%S")
        target = (
            scheduled.hour * 3600
            + scheduled.minute * 60
            + scheduled.second
        )
        if 0 <= seconds - target <= grace_seconds:
            key = f"{today.isoformat()}T{value}"
            if task.get("last_schedule_key") != key:
                return key
    return None

