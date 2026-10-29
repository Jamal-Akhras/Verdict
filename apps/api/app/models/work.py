"""Milestone 3 models: Task (unit of agent work, DAG via depends_on slugs)
and Artifact (immutable, versioned agent output with full provenance).

Orphan artifacts are schema-impossible: task_id and agent_id are NOT NULL
(quality rule #4).
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    review = "review"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class ReviewStatus(str, enum.Enum):
    """Artifact review lifecycle. Stored as a plain String column (no
    migration needed); this enum is the single vocabulary for every
    comparison and assignment - no bare string literals elsewhere."""

    unreviewed = "unreviewed"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    # the founder requested changes; a newer version replaces it
    superseded = "superseded"


class Task(PKMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    agent_slug: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20), default=TaskStatus.queued
    )
    depends_on: Mapped[list[Any]] = mapped_column(JSON, default=list)  # agent slugs
    cost_used_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    # Set when this task redoes work the founder sent back: their directions
    # bind every attempt (including supervisor send-backs), and the new
    # artifact supersedes the old one.
    founder_feedback: Mapped[str] = mapped_column(Text, default="")
    revises_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))


class Artifact(PKMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_slug: Mapped[str] = mapped_column(String(100))
    artifact_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    review_status: Mapped[str] = mapped_column(
        String(20), default=ReviewStatus.unreviewed.value
    )
    model_used: Mapped[str] = mapped_column(String(100), default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
