from pydantic import BaseModel, Field
from typing import List, Optional


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


class TaskUpdate(TaskCreate):
    pass


class Settings(BaseModel):
    auto_enabled: bool = True
    refresh_times: List[str] = Field(default_factory=list)
    webhook_url: str = ""


class ApiResponse(BaseModel):
    ok: bool = True
    data: Optional[dict] = None
    error: Optional[str] = None
