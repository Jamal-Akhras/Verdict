"""Supervision models: ModelProfile (a user-configured model an agent can be
pinned to), ReviewRecord (a supervisor's verdict on one attempt), and Flag
(an escalation climbing the supervisor chain).

The hierarchy itself lives on Agent.supervisor_id: a worker's output is
reviewed by its supervisor; escalations climb supervisor links; an agent
with no supervisor reports to the founder. ReviewRecord is append-only;
Flag.chain grows by one hop per level and is never rewritten.
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class ProviderKind(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    gemini = "gemini"
    local = "local"
    claude_code = "claude_code"
    codex = "codex"


# How each provider is paid for: shown in the UI and used for validation.
ACCESS_BY_PROVIDER: dict[ProviderKind, str] = {
    ProviderKind.openai: "api",
    ProviderKind.anthropic: "api",
    ProviderKind.gemini: "api",
    ProviderKind.local: "local",
    ProviderKind.claude_code: "subscription",
    ProviderKind.codex: "subscription",
}


class ModelTier(str, enum.Enum):
    """`high` = frontier quality (the routing table's high tier). Only high
    tier models may supervise high-risk work or do it unsupervised."""

    high = "high"
    cheap = "cheap"
    local = "local"


class ModelProfile(PKMixin, TimestampMixin, Base):
    __tablename__ = "model_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[ProviderKind] = mapped_column(
        Enum(ProviderKind, native_enum=False, length=20)
    )
    model: Mapped[str] = mapped_column(String(200))
    # local only; empty = settings.local_llm_base_url
    base_url: Mapped[str] = mapped_column(String(500), default="")
    tier: Mapped[ModelTier] = mapped_column(
        Enum(ModelTier, native_enum=False, length=10), default=ModelTier.high
    )
    # USD per 1M tokens actually paid; 0 for local and subscription.
    price_in: Mapped[float] = mapped_column(Float, default=0.0)
    price_out: Mapped[float] = mapped_column(Float, default=0.0)

    @property
    def access(self) -> str:
        return ACCESS_BY_PROVIDER[self.provider]


class ReviewDecision(str, enum.Enum):
    accept = "accept"
    revise = "revise"
    escalate = "escalate"


class ReviewRecord(PKMixin, TimestampMixin, Base):
    """One supervisor review of one worker attempt. Append-only."""

    __tablename__ = "task_reviews"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    worker_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    reviewer_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, native_enum=False, length=10)
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")
    issues: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # The worker output that was reviewed, so the trace shows every draft.
    reviewed_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FlagStatus(str, enum.Enum):
    open = "open"  # climbing the chain
    resolved = "resolved"  # an agent above the raiser settled it
    raised = "raised"  # reached the founder; waiting on them
    approved = "approved"  # founder accepted the work
    denied = "denied"  # founder rejected the work
    revised = "revised"  # founder sent the work back with directions


class Flag(PKMixin, TimestampMixin, Base):
    __tablename__ = "flags"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    raised_by_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    # Who holds it now; None once it reaches the founder or is settled.
    holder_agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"))
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[FlagStatus] = mapped_column(
        Enum(FlagStatus, native_enum=False, length=10), default=FlagStatus.open
    )
    # One hop per level: {agent_id, agent_name, model, decision, rationale, at}
    chain: Mapped[list[Any]] = mapped_column(JSON, default=list)
    resolution: Mapped[str] = mapped_column(Text, default="")
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
