from typing import Literal

from pydantic import BaseModel, Field


class GlobalMenuConfigUpdate(BaseModel):
    version: int = Field(ge=1)
    visibility: dict[str, bool]


class UserMenuOverrideUpdate(BaseModel):
    version: int = Field(ge=1)
    overrides: dict[str, Literal["inherit", "visible", "hidden"]]
