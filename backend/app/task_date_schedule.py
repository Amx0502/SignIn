import datetime as dt


DATE_MODE_DAILY = "daily"
DATE_MODE_SPECIFIC = "specific"
DATE_MODES = {DATE_MODE_DAILY, DATE_MODE_SPECIFIC}
MAX_TASK_DATES = 730


def normalize_date_list(values, field_label: str) -> list[str]:
    if values is None:
        items = []
    elif isinstance(values, (list, tuple, set)):
        items = values
    else:
        raise ValueError(f"{field_label}必须是日期数组")

    normalized: list[str] = []
    for value in items:
        text = str(value).strip()
        if not text:
            continue
        try:
            parsed = dt.date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(
                f"{field_label}中的日期格式无效：{text}，请使用 YYYY-MM-DD"
            ) from exc
        if parsed.isoformat() != text:
            raise ValueError(
                f"{field_label}中的日期格式无效：{text}，请使用 YYYY-MM-DD"
            )
        normalized.append(text)

    result = sorted(set(normalized))
    if len(result) > MAX_TASK_DATES:
        raise ValueError(f"{field_label}最多允许 {MAX_TASK_DATES} 个日期")
    return result


def normalize_task_date_rule(task: dict | None = None) -> dict:
    task = task or {}
    date_mode = str(task.get("date_mode", DATE_MODE_DAILY)).strip().lower()
    if date_mode not in DATE_MODES:
        raise ValueError("执行日期模式只能是每天执行或指定日期")

    run_dates = normalize_date_list(task.get("run_dates", []), "指定执行日期")
    skip_dates = normalize_date_list(task.get("skip_dates", []), "单独跳过日期")
    if date_mode == DATE_MODE_SPECIFIC and not run_dates:
        raise ValueError("指定日期模式下请至少选择一个执行日期")

    return {
        "date_mode": date_mode,
        "run_dates": run_dates,
        "skip_dates": skip_dates,
    }


def is_task_active_on(task: dict, run_date: dt.date) -> bool:
    date_key = run_date.isoformat()
    date_mode = str(task.get("date_mode", DATE_MODE_DAILY)).strip().lower()

    if date_mode == DATE_MODE_SPECIFIC:
        if date_key not in set(task.get("run_dates", []) or []):
            return False
    elif date_mode != DATE_MODE_DAILY:
        return False

    if date_key in set(task.get("skip_dates", []) or []):
        return False
    if task.get("skip_weekends", False) and run_date.weekday() >= 5:
        return False
    return True


def get_last_effective_occurrence(task: dict) -> dt.datetime | None:
    """Return the final runnable date/time for a specific-date task."""
    if (
        str(task.get("date_mode", DATE_MODE_DAILY)).strip().lower()
        != DATE_MODE_SPECIFIC
    ):
        return None

    run_dates = normalize_date_list(task.get("run_dates", []), "指定执行日期")
    effective_dates = [
        dt.date.fromisoformat(value)
        for value in run_dates
        if is_task_active_on(task, dt.date.fromisoformat(value))
    ]
    if not effective_dates:
        return None

    parsed_times: list[dt.time] = []
    for value in task.get("times", []) or []:
        text = str(value).strip()
        try:
            parsed_times.append(dt.time.fromisoformat(text))
        except ValueError:
            continue
    if not parsed_times:
        return None

    return dt.datetime.combine(max(effective_dates), max(parsed_times)).replace(
        microsecond=0
    )
