"""Migration #1 models: User, Project, IdeaSubmission, AuditEvent.

Rules encoded here (see docs: product quality rules):
- AuditEvent is append-only. No update/delete paths exist in the service layer.
- Project.status transitions are validated in services, not by callers.
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class ProjectStatus(str, enum.Enum):
    intake = "intake"
    evaluating = "evaluating"
    awaiting_approval = "awaiting_approval"
    active = "active"
    parked = "parked"
    archived = "archived"


class ProjectStage(str, enum.Enum):
    none = "none"
    kill = "kill"
    park = "park"
    research = "research"
    validate = "validate"
    prototype = "prototype"
    build = "build"


class ActorType(str, enum.Enum):
    user = "user"
    agent = "agent"
    system = "system"


class User(PKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(50), default="free")

    projects: Mapped[list["Project"]] = relationship(back_populates="user")


class Project(PKMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, native_enum=False, length=30), default=ProjectStatus.intake
    )
    stage: Mapped[ProjectStage] = mapped_column(
        Enum(ProjectStage, native_enum=False, length=20), default=ProjectStage.none
    )
    budget_total_usd: Mapped[float] = mapped_column(default=0.0)
    budget_used_usd: Mapped[float] = mapped_column(default=0.0)
    # Founder-authored instructions appended to every agent's system prompt.
    instructions: Mapped[str] = mapped_column(Text, default="")

    user: Mapped["User"] = relationship(back_populates="projects")
    idea_submissions: Mapped[list["IdeaSubmission"]] = relationship(back_populates="project")


class IdeaSubmission(PKMixin, TimestampMixin, Base):
    """Immutable: a revised idea is a new row, never an UPDATE."""

    __tablename__ = "idea_submissions"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalized_brief: Mapped[str | None] = mapped_column(Text)
    missing_info: Mapped[list[Any]] = mapped_column(JSON, default=list)

    project: Mapped["Project"] = relationship(back_populates="idea_submissions")


class AuditEvent(PKMixin, TimestampMixin, Base):
    """Append-only ledger. The product's spine: who/what/when/why."""

    __tablename__ = "audit_events"

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, native_enum=False, length=10))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    subject_type: Mapped[str | None] = mapped_column(String(50))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
