"""Milestone 1 models: FeasibilityReport, ModelCall, CostEvent.

CostEvent and ModelCall are append-only. FeasibilityReport is versioned:
a re-evaluation inserts a new row with version+1, never an UPDATE.
"""
import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class Verdict(str, enum.Enum):
    kill = "kill"
    park = "park"
    research = "research"
    validate = "validate"
    prototype = "prototype"
    build = "build"


class FeasibilityReport(PKMixin, TimestampMixin, Base):
    __tablename__ = "feasibility_reports"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, native_enum=False, length=20))
    confidence: Mapped[int] = mapped_column(Integer)  # 0-100
    scores: Mapped[list[Any]] = mapped_column(JSON, default=list)
    mvp_scope: Mapped[list[Any]] = mapped_column(JSON, default=list)
    do_not_build: Mapped[list[Any]] = mapped_column(JSON, default=list)
    assumptions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    validation_plan: Mapped[list[Any]] = mapped_column(JSON, default=list)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    cost_estimate: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Public share token: set on demand by the owner; grants read-only access
    # to a sanitized verdict via GET /share/{token}. Unguessable, revocable
    # by clearing.
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True)


class CostEvent(PKMixin, TimestampMixin, Base):
    """One model call's cost. Append-only; rolls up to Project.budget_used_usd."""

    __tablename__ = "cost_events"

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_slug: Mapped[str | None] = mapped_column(String(100), index=True)
    task_type: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    # Trace linkage: which task this call served and in what capacity
    # (work | review | triage). Null task_id = project-level (intake etc.).
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    call_role: Mapped[str] = mapped_column(String(20), default="work")

    model_call: Mapped["ModelCall | None"] = relationship(back_populates="cost_event")


class ModelCall(PKMixin, TimestampMixin, Base):
    """Full call record for replay/debug. 1:1 with CostEvent.

    router_decision records why this model was chosen - powers the
    'why this model?' UI and the no-black-box guarantee.
    """

    __tablename__ = "model_calls"

    cost_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cost_events.id"), unique=True)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_prompt: Mapped[str] = mapped_column(Text, default="")
    response_text: Mapped[str] = mapped_column(Text, default="")
    output_schema_name: Mapped[str | None] = mapped_column(String(100))
    parse_ok: Mapped[bool] = mapped_column(default=True)
    router_decision: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    cost_event: Mapped["CostEvent"] = relationship(back_populates="model_call")
