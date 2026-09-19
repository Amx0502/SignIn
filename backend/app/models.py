from pydantic import BaseModel, Field
from typing import List, Literal
from datetime import datetime

from .membership_constants import (
    DEFAULT_CARD_DELETE_DELAY_SECONDS,
    DEFAULT_CARD_TOTAL_USES,
    MAX_CARD_DELETE_DELAY_SECONDS,
    MAX_CARD_TOTAL_USES,
    MIN_CARD_DELETE_DELAY_SECONDS,
    MIN_CARD_TOTAL_USES,
)


class AccountCreate(BaseModel):
    name: str
    mobile: str
    password: str
    token: str = ""


class AccountUpdate(BaseModel):
    name: str
    mobile: str
    password: str
    token: str = ""


class TaskCreate(BaseModel):
    index: int = Field(default=1, ge=1)
    title: str = ""
    times: List[str] = Field(default_factory=list)
    text: str = ""
    fill_name: str = Field(default="", max_length=100)
    fill_values: dict[str, str] = Field(default_factory=dict)
    fill_fields: List[str] | None = None
    pic_path: List[str] = Field(default_factory=list)
    enable: bool = True
    use_location: bool = False
    location_mode: Literal["none", "auto", "map"] | None = None
    location_address: str = Field(default="", max_length=500)
    location_latitude: float | None = Field(default=None, ge=-90, le=90)
    location_longitude: float | None = Field(default=None, ge=-180, le=180)
    skip_weekends: bool = False
    date_mode: str = Field(default="daily", pattern="^(daily|specific)$")
    run_dates: List[str] = Field(default_factory=list, max_length=730)
    skip_dates: List[str] = Field(default_factory=list, max_length=730)
    auto_disable_after_finish: bool = False
    mode: str = "normal"
    notify_wechat: bool = True


class TaskUpdate(TaskCreate):
    pass


class Settings(BaseModel):
    auto_enabled: bool = True
    refresh_times: List[str] = Field(default_factory=list)
    webhook_url: str = ""


class CheckinDelaySettingsUpdate(BaseModel):
    xxqd_min_seconds: int = Field(default=1, ge=0, le=300)
    xxqd_max_seconds: int = Field(default=18, ge=0, le=300)
    class_cube_min_seconds: int = Field(default=1, ge=0, le=300)
    class_cube_max_seconds: int = Field(default=18, ge=0, le=300)
    miaoying_min_seconds: int = Field(default=1, ge=0, le=300)
    miaoying_max_seconds: int = Field(default=18, ge=0, le=300)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user", pattern="^(admin|user)$")
    is_active: bool = True
    platform_scope: Literal["all", "xxqd", "class_cube"] = "all"
    class_cube_account_limit: int | None = Field(default=None, ge=0)
    xxqd_account_limit: int | None = Field(default=None, ge=0)
    location_search_daily_limit: int | None = Field(default=None, ge=0)
    initial_class_cube_account_id: int | None = Field(default=None, gt=0)
    expires_at: datetime | None = None
    card_type: Literal["single", "monthly"] | None = None
    card_delete_delay_seconds: int | None = Field(
        default=None,
        ge=MIN_CARD_DELETE_DELAY_SECONDS,
        le=MAX_CARD_DELETE_DELAY_SECONDS,
    )
    card_total_uses: int = Field(
        default=DEFAULT_CARD_TOTAL_USES,
        ge=MIN_CARD_TOTAL_USES,
        le=MAX_CARD_TOTAL_USES,
    )
    remark: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    role: str = Field(..., pattern="^(admin|user)$")
    is_active: bool
    platform_scope: Literal["all", "xxqd", "class_cube"] = "all"
    class_cube_account_limit: int | None = Field(default=None, ge=0)
    xxqd_account_limit: int | None = Field(default=None, ge=0)
    location_search_daily_limit: int | None = Field(default=None, ge=0)
    expires_at: datetime | None = None
    card_type: Literal["single", "monthly"] | None = None
    card_delete_delay_seconds: int | None = Field(
        default=None,
        ge=MIN_CARD_DELETE_DELAY_SECONDS,
        le=MAX_CARD_DELETE_DELAY_SECONDS,
    )
    card_total_uses: int | None = Field(
        default=None,
        ge=MIN_CARD_TOTAL_USES,
        le=MAX_CARD_TOTAL_USES,
    )
    remark: str | None = Field(default=None, max_length=255)


class PlatformMemberCreate(BaseModel):
    platform_scope: Literal["xxqd", "class_cube"]
    card_type: Literal["single", "monthly"]
    card_delete_delay_seconds: int = Field(
        default=DEFAULT_CARD_DELETE_DELAY_SECONDS,
        ge=MIN_CARD_DELETE_DELAY_SECONDS,
        le=MAX_CARD_DELETE_DELAY_SECONDS,
    )
    card_total_uses: int = Field(
        default=DEFAULT_CARD_TOTAL_USES,
        ge=MIN_CARD_TOTAL_USES,
        le=MAX_CARD_TOTAL_USES,
    )
    remark: str | None = Field(default=None, max_length=255)


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class PurchaseLinkSettingsUpdate(BaseModel):
    purchase_url: str = Field(..., min_length=1, max_length=2048)


