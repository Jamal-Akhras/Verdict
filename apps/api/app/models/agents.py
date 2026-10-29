"""Milestone 2 models: AgentTemplate (versioned blueprint) and Agent (live instance).

State machine for Agent.status is enforced in services/agent_lifecycle.py,
never by callers (quality rule #9).
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class AgentStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    active = "active"
    paused = "paused"
    blocked = "blocked"
    completed = "completed"
    archived = "archived"
    rejected = "rejected"


class Authority(str, enum.Enum):
    observe = "observe"
    suggest = "suggest"
    draft = "draft"


class AgentTemplate(PKMixin, TimestampMixin, Base):
    __tablename__ = "agent_templates"
    __table_args__ = (UniqueConstraint("slug", "version", name="uq_template_slug_version"),)

    slug: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(255))
    initials: Mapped[str] = mapped_column(String(4), default="AG")
    team: Mapped[str] = mapped_column(String(50), default="Strategy")
    role: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text, default="")
    default_tools: Mapped[list[Any]] = mapped_column(JSON, default=list)
    checks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    output_types: Mapped[list[Any]] = mapped_column(JSON, default=list)
    task_types: Mapped[list[Any]] = mapped_column(JSON, default=list)
    default_budget_usd: Mapped[float] = mapped_column(Float, default=1.0)
    risk_level: Mapped[str] = mapped_column(String(10), default="low")
    authority_default: Mapped[Authority] = mapped_column(
        Enum(Authority, native_enum=False, length=10), default=Authority.observe
    )
    approval_requirement: Mapped[str] = mapped_column(String(255), default="none")


class Agent(PKMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_templates.id"))
    slug: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    initials: Mapped[str] = mapped_column(String(4), default="AG")
    team: Mapped[str] = mapped_column(String(50), default="Strategy")
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, native_enum=False, length=20), default=AgentStatus.proposed
    )
    authority: Mapped[Authority] = mapped_column(
        Enum(Authority, native_enum=False, length=10), default=Authority.observe
    )
    risk_level: Mapped[str] = mapped_column(String(10), default="low")
    budget_max_usd: Mapped[float] = mapped_column(Float, default=1.0)
    created_by: Mapped[str] = mapped_column(String(20), default="system")

    # Hierarchy + per-agent configuration (see models/hierarchy.py).
    # None = route by task type through routing.yaml (the original behavior).
    model_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_profiles.id"))
    # Reviews this agent's work and receives its escalations; None = the founder.
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"))
    # Founder-authored, appended to the system prompt (trusted, not fenced).
    instructions: Mapped[str] = mapped_column(Text, default="")
    # Supervisor send-backs allowed before the work must be accepted or escalated.
    max_revisions: Mapped[int] = mapped_column(Integer, default=2)
    # None = the task definition's default founder gate (PRD, tech plan).
    requires_approval: Mapped[bool | None] = mapped_column(default=None)
