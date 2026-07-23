from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class Task(BaseModel):
    index: int = Field(default=1, ge=1)
    title: str = Field(default="")
    times: List[str] = Field(default_factory=list)
    enable: bool = Field(default=True)
    use_location: bool = Field(default=False)
    text: str = Field(default="")
    pic_path: List[str] = Field(default_factory=list)
    skip_weekends: bool = Field(default=False)
    mode: str = Field(default="normal", pattern="^(normal|image)$")
    notify_wechat: bool = Field(default=True)


class Account(BaseModel):
    name: str
    mobile: str
    password: str
    token: str = Field(default="")
    tasks: List[Task] = Field(default_factory=list)


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
    pic_path: List[str] = Field(default_factory=list)
    enable: bool = True
    use_location: bool = False
    skip_weekends: bool = False
    mode: str = "normal"
    notify_wechat: bool = True


class TaskUpdate(TaskCreate):
    pass


class Settings(BaseModel):
    auto_enabled: bool = True
    refresh_times: List[str] = Field(default_factory=list)
    webhook_url: str = ""


class User(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    role: str = "user"
    must_change_password: bool = False


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: dict


class LogoutRequest(BaseModel):
    refresh_token: str = ""


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user", pattern="^(admin|user)$")
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    role: str = Field(..., pattern="^(admin|user)$")
    is_active: bool


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)



