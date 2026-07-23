from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    tasks: Mapped[list["TaskRow"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="TaskRow.position",
        passive_deletes=True,
    )
    projects: Mapped[list["AccountProjectRow"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="AccountProjectRow.position",
        passive_deletes=True,
    )


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("account_id", "position", name="uq_tasks_account_position"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    project_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    times: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    enable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_location: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pic_paths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    skip_weekends: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    notify_wechat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    account: Mapped[AccountRow] = relationship(back_populates="tasks")


class AccountProjectRow(Base):
    __tablename__ = "account_projects"
    __table_args__ = (
        UniqueConstraint("account_id", "position", name="uq_projects_account_position"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    account: Mapped[AccountRow] = relationship(back_populates="projects")
