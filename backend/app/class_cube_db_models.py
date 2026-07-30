from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class ClassCubeBase(DeclarativeBase):
    pass


class ClassCubeAccountRow(ClassCubeBase):
    __tablename__ = "class_cube_accounts"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    remote_user_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    cookie: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    courses: Mapped[list["ClassCubeCourseRow"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list["ClassCubeTaskRow"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ClassCubeCourseRow(ClassCubeBase):
    __tablename__ = "class_cube_courses"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "remote_course_id",
            name="uq_class_cube_courses_account_remote",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    remote_course_id: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_code: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    account: Mapped[ClassCubeAccountRow] = relationship(
        back_populates="courses"
    )
    checkin_items: Mapped[list["ClassCubeCheckinItemRow"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list["ClassCubeTaskRow"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ClassCubeCheckinItemRow(ClassCubeBase):
    __tablename__ = "class_cube_checkin_items"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "remote_item_id",
            "remote_module",
            name="uq_class_cube_items_course_remote_module",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    remote_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    remote_module: Mapped[str] = mapped_column(String(64), nullable=False)
    form_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    form_schema: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    course: Mapped[ClassCubeCourseRow] = relationship(
        back_populates="checkin_items"
    )
    task_runs: Mapped[list["ClassCubeTaskRunRow"]] = relationship(
        back_populates="checkin_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    task_item_claims: Mapped[list["ClassCubeTaskItemClaimRow"]] = relationship(
        back_populates="checkin_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ClassCubeTaskRow(ClassCubeBase):
    __tablename__ = "class_cube_tasks"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 7), nullable=True
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(11, 7), nullable=True
    )
    accuracy: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    photo_path: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
    )
    password: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    schedule_times_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notify_wecom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_schedule_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default=""
    )
    last_scan_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    account: Mapped[ClassCubeAccountRow] = relationship(
        back_populates="tasks"
    )
    course: Mapped[ClassCubeCourseRow] = relationship(back_populates="tasks")
    runs: Mapped[list["ClassCubeTaskRunRow"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    item_claims: Mapped[list["ClassCubeTaskItemClaimRow"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ClassCubeTaskRunRow(ClassCubeBase):
    __tablename__ = "class_cube_task_runs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="task", index=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    checkin_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_checkin_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    remote_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_summary: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    task: Mapped[ClassCubeTaskRow | None] = relationship(
        back_populates="runs"
    )
    checkin_item: Mapped[ClassCubeCheckinItemRow | None] = relationship(
        back_populates="task_runs"
    )
    item_claims: Mapped[list["ClassCubeTaskItemClaimRow"]] = relationship(
        back_populates="last_run",
        passive_deletes=True,
    )


class ClassCubeTaskItemClaimRow(ClassCubeBase):
    __tablename__ = "class_cube_task_item_claims"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "remote_module",
            "remote_item_id",
            name="uq_class_cube_claims_task_remote",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checkin_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_checkin_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    remote_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    remote_module: Mapped[str] = mapped_column(
        String(32), nullable=False, default="punchs"
    )
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processing"
    )
    last_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("class_cube_task_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    lease_token: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    phase: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pre_submit"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    task: Mapped[ClassCubeTaskRow] = relationship(back_populates="item_claims")
    checkin_item: Mapped[ClassCubeCheckinItemRow] = relationship(
        back_populates="task_item_claims"
    )
    last_run: Mapped[ClassCubeTaskRunRow | None] = relationship(
        back_populates="item_claims"
    )
