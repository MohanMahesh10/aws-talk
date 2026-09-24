"""SQLAlchemy persistence models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.utcnow()


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="EMPLOYEE")
    department: Mapped[str] = mapped_column(String(64), default="Sales")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(32), index=True)
    employee_name: Mapped[str] = mapped_column(String(120))
    trip_purpose: Mapped[str] = mapped_column(String(255))
    trip_location: Mapped[str] = mapped_column(String(120))
    trip_start: Mapped[str] = mapped_column(String(32))
    trip_end: Mapped[str] = mapped_column(String(32))
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    state: Mapped[str] = mapped_column(String(32), default="UPLOADED", index=True)
    policy_version: Mapped[str] = mapped_column(String(16), default="v1")
    required_approver: Mapped[str] = mapped_column(String(64), default="")
    policy_reason: Mapped[str] = mapped_column(String(255), default="")
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    extraction_source: Mapped[str] = mapped_column(String(32), default="demo")
    injection_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    loop_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_reason: Mapped[str] = mapped_column(String(255), default="")
    demo_scenario: Mapped[str] = mapped_column(String(64), default="")
    payment_status: Mapped[str] = mapped_column(String(32), default="")
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    expenses: Mapped[list[Expense]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    approvals: Mapped[list[Approval]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    events: Mapped[list[AuditEvent]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    traces: Mapped[list[ToolTrace]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    payments: Mapped[list[PaymentAttempt]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    files: Mapped[list[ClaimFile]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class ClaimFile(Base):
    __tablename__ = "claim_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(64), default="application/octet-stream")

    claim: Mapped[Claim] = relationship(back_populates="files")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    vendor: Mapped[str] = mapped_column(String(120))
    expense_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    date: Mapped[str] = mapped_column(String(32), default="")
    invoice_number: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    filename: Mapped[str] = mapped_column(String(255), default="")
    route: Mapped[str] = mapped_column(String(64), default="")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    injection_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_text: Mapped[str] = mapped_column(Text, default="")

    claim: Mapped[Claim] = relationship(back_populates="expenses")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    required_role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    decided_by: Mapped[str] = mapped_column(String(120), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str] = mapped_column(String(255), default="")

    claim: Mapped[Claim] = relationship(back_populates="approvals")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)
    message: Mapped[str] = mapped_column(String(512))
    actor: Mapped[str] = mapped_column(String(64), default="reem")
    event_type: Mapped[str] = mapped_column(String(32), default="info")

    claim: Mapped[Claim] = relationship(back_populates="events")


class ToolTrace(Base):
    __tablename__ = "tool_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    input_data: Mapped[str] = mapped_column(Text, default="")
    output_data: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(String(255), default="")
    parallel: Mapped[bool] = mapped_column(Boolean, default=False)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    claim: Mapped[Claim] = relationship(back_populates="traces")


class PolicyConfig(Base):
    __tablename__ = "policy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    rules_json: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PolicyChange(Base):
    __tablename__ = "policy_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_version: Mapped[str] = mapped_column(String(16))
    to_version: Mapped[str] = mapped_column(String(16))
    changed_by: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EmployeeMemory(Base):
    __tablename__ = "employee_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    employee_name: Mapped[str] = mapped_column(String(120), default="")
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    last_vendors: Mapped[str] = mapped_column(String(512), default="")
    last_total: Mapped[float] = mapped_column(Float, default=0.0)
    last_approver: Mapped[str] = mapped_column(String(64), default="")
    last_policy_version: Mapped[str] = mapped_column(String(16), default="")
    last_claim_id: Mapped[str] = mapped_column(String(32), default="")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_pk: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    claim: Mapped[Claim] = relationship(back_populates="payments")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(32), index=True)
    recipient_role: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
