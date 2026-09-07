from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MiaoyingAccountUpdate(BaseModel):
    remark: str = ""
    real_name: str = ""
    school_no: str = ""
    class_name: str = ""
    enabled: bool = True


class MiaoyingSettingsUpdate(BaseModel):
    miaoying_webhook_url: str = Field(default="", max_length=2048)


class MiaoyingManualCheckin(BaseModel):
    account_id: int = Field(gt=0)
    location_name: str = Field(default="", max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    notify_wecom: bool = True
    answers: dict[str, Any] = Field(default_factory=dict)


class MiaoyingTaskPayload(BaseModel):
    account_id: int
    form_id: int
    name: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    schedule_times: list[str] = Field(default_factory=lambda: ["08:00:00"])
    start_date: date | None = None
    end_date: date | None = None
    date_mode: str = "daily"
    run_dates: list[str] = Field(default_factory=list)
    skip_dates: list[str] = Field(default_factory=list)
    skip_weekends: bool = False
    auto_disable_after_finish: bool = True
    location_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    answers: dict[str, Any] = Field(default_factory=dict)

    @field_validator("date_mode")
    @classmethod
    def validate_mode(cls, value: str):
        if value not in {"daily", "specific"}:
            raise ValueError("日期模式仅支持 daily 或 specific")
        return value

    @field_validator("schedule_times")
    @classmethod
    def validate_times(cls, values: list[str]):
        import datetime
        result = []
        for value in values:
            datetime.time.fromisoformat(value)
            if value not in result:
                result.append(value)
        if not result:
            raise ValueError("至少设置一个执行时间")
        return sorted(result)


class MiaoyingBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1)
