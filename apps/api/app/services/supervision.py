"""Supervised execution: workers draft, supervisors review, escalations
climb the hierarchy and reach the founder only when nobody can settle them.

The economics: worker agents run on local models (no per-token price, no
rate limits) and produce the bulk of the tokens; frontier models -
API or subscription - only read and judge. A supervisor sends a draft back
with feedback up to the worker's max_revisions, then must accept or
escalate. Each level above triages: resolve with binding guidance, or pass
it up. The founder sees only what the top of the chain could not settle.

Every step is on the record: each model call is a CostEvent+ModelCall
tagged with the task and its role (work/review/triage), each review is a
ReviewRecord holding the exact draft it judged, and each escalation is a
Flag whose chain records every hop.
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.base import (
    INJECTION_GUARD,
    fence_team_document,
    fence_user_input,
    load_prompt,
    with_founder_instructions,
)
from app.agents.build_agents import Revision, TaskDef, execute_task_def
from app.models.agents import Agent, AgentStatus
from app.models.ai import CostEvent
from app.models.base import utcnow
from app.models.core import ActorType, Project
from app.models.hierarchy import Flag, FlagStatus, ModelProfile, ReviewDecision, ReviewRecord
from app.models.work import Artifact, Task, TaskStatus
from app.providers.router import ModelRouter
from app.services.audit import record_event

logger = logging.getLogger(__name__)

# Agents in these states may review and triage. A paused or blocked
# supervisor is skipped: its own supervisor covers for it.
REVIEWING_STATUSES = {AgentStatus.approved, AgentStatus.active, AgentStatus.completed}

# Supervisors see the whole draft, not the 6k-char downstream summary.
DRAFT_CHAR_BUDGET = 30_000


class ReviewIssue(BaseModel):
    severity: str = "medium"
    issue: str
    where: str = ""


class SupervisorReviewOutput(BaseModel):
    decision: Literal["accept", "revise", "escalate"]
    summary: str
    feedback: str = ""
    issues: list[ReviewIssue] = []
    escalation_title: str = ""
    escalation_detail: str = ""

    @model_validator(mode="after")
    def decision_has_payload(self) -> "SupervisorReviewOutput":
        if self.decision == "revise" and not self.feedback.strip():
            raise ValueError("decision=revise requires specific feedback for the worker")
        if self.decision == "escalate" and not self.escalation_title.strip():
            raise ValueError("decision=escalate requires an escalation_title")
        return self


class TriageOutput(BaseModel):
    decision: Literal["resolve", "escalate"]
    rationale: str
    resolution: str = ""
    question: str = ""
    severity: str = "medium"

    @model_validator(mode="after")
    def decision_has_payload(self) -> "TriageOutput":
        if self.decision == "resolve" and not self.resolution.strip():
            raise ValueError("decision=resolve requires a resolution")
        return self


class SupervisionError(Exception):
    """Supervision could not proceed (e.g. a supervisor's budget is spent)."""


@dataclass
class SupervisedResult:
    output: BaseModel
    attempts: int = 1
    # Set when the escalation reached the founder; the caller gates on it.
    raised_flag: Flag | None = None
    # Binding guidance from agents that resolved escalations below the founder.
    resolutions: list[str] = field(default_factory=list)


def spend(db: Session, project_id: uuid.UUID, slug: str) -> float:
    return db.scalar(
        select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)).where(
            CostEvent.project_id == project_id, CostEvent.agent_slug == slug
        )
    )


def effective_supervisor(db: Session, agent: Agent) -> Agent | None:
    """The nearest supervisor up the chain able to act right now, or None
    (= the founder). Cycle-safe even though config validation forbids cycles."""
    seen = {agent.id}
    current = agent
    while current.supervisor_id is not None and current.supervisor_id not in seen:
        seen.add(current.supervisor_id)
        boss = db.get(Agent, current.supervisor_id)
        if boss is None:
            return None
        if boss.status in REVIEWING_STATUSES:
            return boss
        current = boss
    return None


def _profile(db: Session, agent: Agent) -> ModelProfile | None:
    return db.get(ModelProfile, agent.model_profile_id) if agent.model_profile_id else None


def _model_label(db: Session, agent: Agent) -> str:
    profile = _profile(db, agent)
    return f"{profile.name} ({profile.access})" if profile else "routing table"


def render_draft(output: BaseModel) -> str:
    text = json.dumps(output.model_dump(), indent=1, default=str)
    if len(text) > DRAFT_CHAR_BUDGET:
        text = text[:DRAFT_CHAR_BUDGET] + "\n... [draft truncated for length]"
    return text


def _remaining(db: Session, project_id: uuid.UUID, agent: Agent) -> float:
    left = agent.budget_max_usd - spend(db, project_id, agent.slug)
    if left <= 0.01:
        raise SupervisionError(f"{agent.name}'s budget is exhausted")
    return left


def _agent_system_prompt(prompt_file: str, agent: Agent, project: Project) -> str:
    base = (
        f"{load_prompt(prompt_file)}\n\n"
        f"You are {agent.name}. Your role on this team: {agent.role}"
    )
    return with_founder_instructions(
        base, project=project.instructions, agent=agent.instructions
    )


def _review(
    db: Session, router: ModelRouter, *, project: Project, task: Task, task_def: TaskDef,
    worker: Agent, reviewer: Agent, brief: str, draft: str, attempt: int,
    revisions_left: int, history: list[ReviewRecord],
) -> SupervisorReviewOutput:
    options = (
        "accept, revise, or escalate" if revisions_left > 0
        else "accept or escalate - the worker has used all its revisions, so "
             "revise is not available"
    )
    prior = "\n".join(
        f"- attempt {r.attempt}: {r.decision.value} - {r.summary}" for r in history
    ) or "- none"
    # The worker's spec includes any changes the founder requested, so the
    # supervisor holds the draft to them too.
    worker_spec = with_founder_instructions(
        load_prompt(task_def.prompt_file),
        project=project.instructions, agent=worker.instructions,
        directions=task.founder_feedback,
    )
    user_prompt = (
        f"{INJECTION_GUARD}\n\n"
        f"Task: {task.title}\n"
        f"Worker: {worker.name} (model: {_model_label(db, worker)})\n"
        f"Attempt: {attempt}. Your options this time: {options}.\n\n"
        f"Your earlier reviews of this task:\n{prior}\n\n"
        f"Idea brief:\n{fence_user_input(brief)}\n\n"
        "The worker's full instructions (what it was asked to produce):\n"
        f"{fence_team_document('Worker instructions', 'system', worker_spec)}\n\n"
        "The draft under review:\n"
        f"{fence_team_document(f'{task_def.artifact_title} draft', worker.slug, draft)}"
    )
    profile = _profile(db, reviewer)
    return router.run(
        db,
        task_type="supervisor_review",
        output_schema=SupervisorReviewOutput,
        system_prompt=_agent_system_prompt("supervisor", reviewer, project),
        user_prompt=user_prompt,
        risk_level=task_def.risk_level,
        max_cost_usd=_remaining(db, project.id, reviewer),
        max_tokens=3000,
        project_id=project.id,
        agent_slug=reviewer.slug,
        pinned=profile,
        task_id=task.id,
        call_role="review",
    )


def _triage(
    db: Session, router: ModelRouter, *, project: Project, task: Task, task_def: TaskDef,
    holder: Agent, flag: Flag, draft: str,
) -> TriageOutput:
    above = effective_supervisor(db, holder)
    position = f"You report to {above.name}." if above else "You report directly to the founder."
    hops = "\n".join(
        f"- {h['agent_name']}: {h['decision']} - {h['rationale']}" for h in flag.chain
    )
    escalation = f"{flag.title}\n\n{flag.detail}\n\nHops so far:\n{hops}"
    user_prompt = (
        f"{INJECTION_GUARD}\n\n"
        f"{position}\n"
        f"Task: {task.title} (artifact: {task_def.artifact_title})\n\n"
        "The escalation:\n"
        f"{fence_team_document('Escalation', 'team', escalation)}\n\n"
        "The work in question:\n"
        f"{fence_team_document(f'{task_def.artifact_title} draft', task.agent_slug, draft)}"
    )
    return router.run(
        db,
        task_type="escalation_triage",
        output_schema=TriageOutput,
        system_prompt=_agent_system_prompt("escalation", holder, project),
        user_prompt=user_prompt,
        risk_level="medium",
        max_cost_usd=_remaining(db, project.id, holder),
        max_tokens=2000,
        project_id=project.id,
        agent_slug=holder.slug,
        pinned=_profile(db, holder),
        task_id=task.id,
        call_role="triage",
    )


def _hop(db: Session, agent: Agent, decision: str, rationale: str) -> dict:
    return {
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "model": _model_label(db, agent),
        "decision": decision,
        "rationale": rationale,
        "at": utcnow().isoformat(),
    }


def _climb(
    db: Session, router: ModelRouter, *, project: Project, task: Task, task_def: TaskDef,
    flag: Flag, raiser: Agent, draft: str,
) -> None:
    """Walk the flag up the hierarchy until someone resolves it or it
    reaches the founder (status=raised)."""
    holder = effective_supervisor(db, raiser)
    while holder is not None:
        flag.holder_agent_id = holder.id
        db.flush()
        result = _triage(db, router, project=project, task=task, task_def=task_def,
                         holder=holder, flag=flag, draft=draft)
        hop = _hop(db, holder, result.decision, result.rationale)
        # reassign, don't mutate: JSON columns only persist on assignment
        flag.chain = [*flag.chain, hop]
        if result.decision == "resolve":
            flag.status = FlagStatus.resolved
            flag.resolution = result.resolution
            flag.holder_agent_id = None
            record_event(
                db, event_type="flag.resolved",
                summary=f"{holder.name} resolved '{flag.title}' (level {len(flag.chain)})",
                actor_type=ActorType.agent, actor_id=holder.id, project_id=project.id,
                subject_type="flag", subject_id=flag.id,
                payload={"resolution": result.resolution},
            )
            return
        if result.question.strip():
            flag.detail = result.question
        flag.severity = result.severity
        record_event(
            db, event_type="flag.escalated",
            summary=f"{holder.name} escalated '{flag.title}'",
            actor_type=ActorType.agent, actor_id=holder.id, project_id=project.id,
            subject_type="flag", subject_id=flag.id,
        )
        holder = effective_supervisor(db, holder)
    flag.status = FlagStatus.raised
    flag.holder_agent_id = None
    record_event(
        db, event_type="flag.raised",
        summary=f"'{flag.title}' reached the founder after {len(flag.chain)} hop(s)",
        actor_type=ActorType.system, project_id=project.id,
        subject_type="flag", subject_id=flag.id,
    )


def run_supervised(
    db: Session,
    router: ModelRouter,
    *,
    project: Project,
    task: Task,
    worker: Agent,
    task_def: TaskDef,
    brief: str,
    upstream_context: str,
) -> SupervisedResult:
    """Produce the task's output under supervision. Raises on worker or
    supervisor failure (the orchestrator records it on the task)."""
    revision: Revision | None = None
    history: list[ReviewRecord] = []
    attempt = 0
    returned = ""
    if task.revises_artifact_id is not None:
        previous = db.get(Artifact, task.revises_artifact_id)
        if previous is not None:
            returned = json.dumps(previous.content, indent=1, default=str)[:DRAFT_CHAR_BUDGET]
    while True:
        attempt += 1
        output = execute_task_def(
            db, router, task_def=task_def, project_id=project.id,
            brief=brief, upstream_context=upstream_context,
            max_cost_usd=_remaining(db, project.id, worker),
            agent_slug=worker.slug, pinned=_profile(db, worker),
            project_instructions=project.instructions,
            agent_instructions=worker.instructions,
            revision=revision, task_id=task.id,
            founder_directions=task.founder_feedback,
            founder_returned_output=returned,
        )
        reviewer = effective_supervisor(db, worker)
        if reviewer is None:
            return SupervisedResult(output=output, attempts=attempt)

        task.status = TaskStatus.review
        db.commit()  # make 'in review' visible while the supervisor reads
        draft = render_draft(output)
        revisions_left = worker.max_revisions - (attempt - 1)
        review = _review(
            db, router, project=project, task=task, task_def=task_def, worker=worker,
            reviewer=reviewer, brief=brief, draft=draft, attempt=attempt,
            revisions_left=revisions_left, history=history,
        )
        decision = review.decision
        forced = decision == "revise" and revisions_left <= 0
        if forced:
            # The schema can't know the revision budget; a send-back past it
            # becomes an escalation rather than an infinite loop.
            decision = "escalate"
        record = ReviewRecord(
            project_id=project.id, task_id=task.id, worker_agent_id=worker.id,
            reviewer_agent_id=reviewer.id, attempt=attempt,
            decision=ReviewDecision(decision), summary=review.summary,
            feedback=review.feedback, issues=[i.model_dump() for i in review.issues],
            reviewed_output=output.model_dump(),
        )
        db.add(record)
        db.flush()
        history.append(record)
        record_event(
            db, event_type=f"review.{decision}",
            summary=f"{reviewer.name} reviewed {worker.name}'s draft "
                    f"(attempt {attempt}): {decision}",
            actor_type=ActorType.agent, actor_id=reviewer.id, project_id=project.id,
            subject_type="task", subject_id=task.id,
            payload={"summary": review.summary, "issues": len(review.issues)},
        )

        if decision == "accept":
            task.status = TaskStatus.running
            return SupervisedResult(output=output, attempts=attempt)

        if decision == "revise":
            revision = Revision(
                reviewer=reviewer.name, attempt=attempt,
                feedback=review.feedback, previous_output=draft,
            )
            task.status = TaskStatus.running
            db.commit()
            continue

        # escalate
        if forced:
            title = f"{worker.name}'s work still needs changes after {attempt} attempts"
            detail = (f"{reviewer.name} wanted another revision but the revision limit "
                      f"({worker.max_revisions}) is reached.\n\n{review.feedback}")
        else:
            title, detail = review.escalation_title, review.escalation_detail
        severities = [i.severity for i in review.issues]
        flag = Flag(
            project_id=project.id, task_id=task.id, raised_by_agent_id=reviewer.id,
            severity=next((s for s in ("critical", "high", "medium") if s in severities), "low"),
            title=title[:255], detail=detail or review.summary,
            chain=[_hop(db, reviewer, "escalate", review.summary)],
        )
        db.add(flag)
        db.flush()
        record_event(
            db, event_type="flag.opened",
            summary=f"{reviewer.name} escalated '{flag.title}'",
            actor_type=ActorType.agent, actor_id=reviewer.id, project_id=project.id,
            subject_type="flag", subject_id=flag.id,
        )
        _climb(db, router, project=project, task=task, task_def=task_def,
               flag=flag, raiser=reviewer, draft=draft)
        task.status = TaskStatus.running
        if flag.status == FlagStatus.raised:
            return SupervisedResult(output=output, attempts=attempt, raised_flag=flag)
        return SupervisedResult(output=output, attempts=attempt,
                                resolutions=[flag.resolution])
