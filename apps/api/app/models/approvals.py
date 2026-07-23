"""Milestone 5: ApprovalRequest - the human gate as a first-class row,
not a framework interrupt (ADR 0001)."""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"


class ApprovalRequest(PKMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(50))  # artifact | agent | budget
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    requested_by_slug: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    blocking: Mapped[bool] = mapped_column(default=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False, length=10), default=ApprovalStatus.pending
    )
    resolution_note: Mapped[str] = mapped_column(Text, default="")
