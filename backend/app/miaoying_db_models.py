from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MiaoyingBase(DeclarativeBase):
    pass


PK = BigInteger().with_variant(Integer, "sqlite")


class MiaoyingQrSessionRow(MiaoyingBase):
    __tablename__ = "miaoying_qr_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    remote_scene_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    qr_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MiaoyingAccountRow(MiaoyingBase):
    __tablename__ = "miaoying_accounts"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    remote_user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    real_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    school_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class MiaoyingFormRow(MiaoyingBase):
    __tablename__ = "miaoying_forms"
    __table_args__ = (UniqueConstraint("account_id", "remote_tongji_id", name="uq_miaoying_form_remote"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("miaoying_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    remote_tongji_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class MiaoyingTaskRow(MiaoyingBase):
    __tablename__ = "miaoying_tasks"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("miaoying_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    form_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("miaoying_forms.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schedule_times: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    run_dates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skip_dates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skip_weekends: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_disable_after_finish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    latitude: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    answer_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_schedule_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class MiaoyingRunRow(MiaoyingBase):
    __tablename__ = "miaoying_runs"
    __table_args__ = (UniqueConstraint("task_id", "schedule_key", name="uq_miaoying_run_schedule"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("miaoying_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    form_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    schedule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduler")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    remote_submission_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MiaoyingSubmissionAuditRow(MiaoyingBase):
    """Sanitized audit trail for outbound Miaoying check-in submissions."""

    __tablename__ = "miaoying_submission_audits"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    form_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    operation: Mapped[str] = mapped_column(String(64), nullable=False, default="createBaomingByInput")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    remote_submission_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    request_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
