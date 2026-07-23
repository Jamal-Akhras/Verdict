"""Task orchestrator: a Postgres-backed DAG runner with failure isolation.

Deliberately boring and inspectable (ADR 0001): topological execution,
one task at a time, commit after every state change so the UI can watch
progress live. A failed task blocks its agent and cancels downstream
tasks; independent branches keep running.
"""
import json
import logging
import uuid
from collections.abc import Callable
from datetime import timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.agents.build_agents import DEFS_BY_SLUG, execute_task_def
from app.models.agents import Agent, AgentStatus
from app.models.approvals import ApprovalRequest, ApprovalStatus
from app.models.ai import CostEvent
from app.models.base import utcnow
from app.models.core import ActorType, IdeaSubmission, Project
from app.models.work import Artifact, ReviewStatus, Task, TaskStatus
from app.providers.router import ModelRouter
from app.services.agent_lifecycle import transition
from app.services.audit import record_event

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]

ORPHAN_ERROR = "orphaned by process restart"


class RunError(Exception):
    pass


def sweep_stale_runs(db: Session, max_age_minutes: int = 30) -> int:
    """Fail tasks abandoned by a dead process so their projects can run again.

    Invariant restored: queued/running tasks exist only while a live process
    is executing them or a blocking approval is pending. A task `running`
    longer than max_age_minutes, or `queued` that long with no live running
    sibling and no pending blocking approval, was orphaned by a restart -
    without this sweep it blocks create_run's in-flight guard forever.
    Returns the number of tasks failed. Caller owns the commit.
    """
    cutoff = utcnow() - timedelta(minutes=max_age_minutes)

    def stale(task: Task) -> bool:
        ts = task.updated_at or task.created_at
        if ts.tzinfo is None:  # sqlite returns naive datetimes
            ts = ts.replace(tzinfo=timezone.utc)
        return ts < cutoff

    inflight = list(
        db.scalars(
            select(Task).where(Task.status.in_([TaskStatus.queued, TaskStatus.running]))
        )
    )
    live_projects = {  # projects with a running task that is still fresh
        t.project_id for t in inflight if t.status == TaskStatus.running and not stale(t)
    }
    orphaned: list[Task] = []
    for t in inflight:
        if not stale(t) or t.project_id in live_projects:
            continue
        if t.status == TaskStatus.queued:
            # A run legitimately parks queued tasks at an approval gate;
            # only sweep when nothing is pending for the founder.
            gate = db.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.project_id == t.project_id,
                    ApprovalRequest.status == ApprovalStatus.pending,
                    ApprovalRequest.blocking.is_(True),
                )
            )
            if gate is not None:
                continue
        orphaned.append(t)

    for t in orphaned:
        t.status = TaskStatus.failed
        t.error = ORPHAN_ERROR
        record_event(
            db, event_type="task.failed",
            summary=f"'{t.title}' {ORPHAN_ERROR}",
            actor_type=ActorType.system, project_id=t.project_id,
            subject_type="task", subject_id=t.id,
        )
    if orphaned:
        db.flush()
        logger.info("sweep_stale_runs: failed %d orphaned task(s)", len(orphaned))
    return len(orphaned)


def create_run(db: Session, project: Project) -> list[Task]:
    """Create queued tasks for every approved agent that has a task definition.
    Refuses if a run is already in flight."""
    # Cost-bomb defense: a run is the most expensive thing a request can start.
    from app.services.limits import daily_spend_exceeded

    exceeded = daily_spend_exceeded(db)
    if exceeded:
        raise RunError(exceeded)
    # Serialize concurrent create_run calls per project: the count-then-insert
    # guard below races without it. Postgres-only; sqlite (tests) is
    # single-writer already.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:pid))"),
            {"pid": str(project.id)},
        )
    # Self-heal before the guard: a run orphaned by a process restart must
    # not brick the project forever.
    sweep_stale_runs(db)
    active = db.scalar(
        select(func.count(Task.id)).where(
            Task.project_id == project.id,
            Task.status.in_([TaskStatus.queued, TaskStatus.running]),
        )
    )
    if active:
        raise RunError("A run is already in progress")

    agents = {
        a.slug: a
        for a in db.scalars(
            select(Agent).where(
                Agent.project_id == project.id,
                Agent.status.in_([AgentStatus.approved, AgentStatus.active]),
            )
        )
    }
    staffed = [d for d in DEFS_BY_SLUG.values() if d.agent_slug in agents]
    if not staffed:
        raise RunError("No approved agents with work to do - approve the team first")

    tasks: list[Task] = []
    for d in staffed:
        deps = [dep for dep in d.depends_on if dep in agents]
        task = Task(
            project_id=project.id,
            agent_id=agents[d.agent_slug].id,
            agent_slug=d.agent_slug,
            title=d.title,
            task_type=d.task_type,
            depends_on=deps,
        )
        db.add(task)
        tasks.append(task)
    db.flush()
    record_event(
        db, event_type="run.created",
        summary=f"Run created with {len(tasks)} tasks",
        actor_type=ActorType.user, project_id=project.id,
        payload={"tasks": [t.title for t in tasks]},
    )
    return tasks


def _agent_spend(db: Session, project_id: uuid.UUID, slug: str) -> float:
    return db.scalar(
        select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)).where(
            CostEvent.project_id == project_id, CostEvent.agent_slug == slug
        )
    )


# Agents whose prompts reference the approved MVP scope: they must actually
# receive it (fixes the wiring bug where "approved MVP scope" was never
# supplied to the Product agent or QA's scope-creep check).
SCOPE_AWARE_SLUGS = {"product", "qa", "cto-architecture", "engineering-planner"}


def _brief(db: Session, project_id: uuid.UUID, agent_slug: str | None = None) -> str:
    sub = db.scalar(
        select(IdeaSubmission)
        .where(IdeaSubmission.project_id == project_id)
        .order_by(IdeaSubmission.created_at.desc())
    )
    brief = (sub.normalized_brief or sub.raw_text) if sub else "No brief recorded."
    if agent_slug in SCOPE_AWARE_SLUGS:
        scope = _feasibility_context(db, project_id)
        if scope:
            brief = f"{brief}\n\n{scope}"
    return brief


def _feasibility_context(db: Session, project_id: uuid.UUID) -> str:
    """The approved MVP scope from the latest feasibility report, rendered
    for downstream prompts. Empty string when no report exists."""
    from app.models.ai import FeasibilityReport

    report = db.scalar(
        select(FeasibilityReport)
        .where(FeasibilityReport.project_id == project_id)
        .order_by(FeasibilityReport.version.desc())
    )
    if report is None:
        return ""

    def bullets(items: list) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- (none listed)"

    return (
        "Approved MVP scope (from the feasibility report - stay strictly inside it):\n"
        f"{bullets(report.mvp_scope)}\n\n"
        "Do NOT build (explicitly out of scope):\n"
        f"{bullets(report.do_not_build)}\n\n"
        "Key assumptions behind the verdict:\n"
        f"{bullets(report.assumptions)}"
    )


# Rendering budget for upstream artifacts: readable per-key text, never a
# mid-JSON cut (the old json.dumps(content)[:6000] truncated mid-token).
ARTIFACT_CHAR_BUDGET = 6000
PER_KEY_CHAR_BUDGET = 1500


def _render_value(value, limit: int) -> str:
    if isinstance(value, str):
        if len(value) > limit:
            return value[:limit].rsplit(" ", 1)[0] + " ...[truncated]"
        return value
    if isinstance(value, list):
        lines: list[str] = []
        used = 0
        for item in value:
            piece = item if isinstance(item, str) else json.dumps(item, default=str)
            if used + len(piece) > limit:
                lines.append(f"  ... (+{len(value) - len(lines)} more items omitted)")
                break
            lines.append(f"  - {piece}")
            used += len(piece)
        return "\n" + "\n".join(lines) if lines else "(empty list)"
    if isinstance(value, dict):
        piece = json.dumps(value, default=str)
        # whole object or nothing - no mid-JSON cuts
        return piece if len(piece) <= limit else "(object omitted for length)"
    return str(value)


def _render_artifact(content) -> str:
    if not isinstance(content, dict):
        return _render_value(content, PER_KEY_CHAR_BUDGET)
    lines: list[str] = []
    used = 0
    for key, value in content.items():
        rendered = f"{key}: {_render_value(value, PER_KEY_CHAR_BUDGET)}"
        if used + len(rendered) > ARTIFACT_CHAR_BUDGET:
            lines.append("... (remaining sections omitted for length)")
            break
        lines.append(rendered)
        used += len(rendered)
    return "\n".join(lines)


def _upstream_context(db: Session, project_id: uuid.UUID, dep_slugs: list) -> str:
    from app.agents.base import fence_team_document

    if not dep_slugs:
        return ""
    parts = []
    for slug in dep_slugs:
        artifact = db.scalar(
            select(Artifact)
            .where(Artifact.project_id == project_id, Artifact.agent_slug == slug)
            .order_by(Artifact.version.desc())
        )
        if artifact:
            parts.append(fence_team_document(
                artifact.title, artifact.agent_slug, _render_artifact(artifact.content)
            ))
    return "\n\n".join(parts)


def run_project(
    project_id: uuid.UUID, router: ModelRouter, session_factory: SessionFactory
) -> None:
    """Execute all queued tasks for a project. Own sessions, commit per step
    so progress is visible while running. Never raises: failures land in
    task.error and the audit log."""
    while True:
        with session_factory() as db:
            task = _next_runnable(db, project_id)
            if task is None:
                _finish_agents(db, project_id)
                db.commit()
                return
            task_id = task.id
            try:
                _execute_one(db, project_id, task_id, router)
                db.commit()
            except Exception:
                # _execute_one handles expected provider/parse failures;
                # anything reaching here is a bug or infra fault. Log it and
                # fail the task so the run doesn't vanish silently.
                logger.exception(
                    "run_project: unexpected error on task %s (project %s)",
                    task_id, project_id,
                )
                db.rollback()
                try:
                    task = db.get(Task, task_id)
                    if task is not None and task.status in (
                        TaskStatus.queued, TaskStatus.running
                    ):
                        task.status = TaskStatus.failed
                        task.error = "unexpected orchestrator error; see server logs"
                        record_event(
                            db, event_type="task.failed",
                            summary=f"'{task.title}' failed with an unexpected error",
                            actor_type=ActorType.system, project_id=project_id,
                            subject_type="task", subject_id=task_id,
                        )
                        db.commit()
                except Exception:
                    logger.exception(
                        "run_project: could not mark task %s failed; aborting run",
                        task_id,
                    )
                    return


def _next_runnable(db: Session, project_id: uuid.UUID) -> Task | None:
    tasks = list(db.scalars(select(Task).where(Task.project_id == project_id)))
    by_slug: dict[str, list[Task]] = {}
    for t in tasks:
        by_slug.setdefault(t.agent_slug, []).append(t)

    def slug_done(slug: str) -> bool:
        return all(t.status == TaskStatus.done for t in by_slug.get(slug, [])) and slug in by_slug

    def slug_dead(slug: str) -> bool:
        return any(
            t.status in (TaskStatus.failed, TaskStatus.cancelled) for t in by_slug.get(slug, [])
        )

    def latest_artifact(slug: str) -> Artifact | None:
        return db.scalar(
            select(Artifact)
            .where(Artifact.project_id == project_id, Artifact.agent_slug == slug)
            .order_by(Artifact.version.desc())
        )

    def cancel(t: Task, reason: str) -> None:
        t.status = TaskStatus.cancelled
        t.error = reason
        record_event(
            db, event_type="task.cancelled",
            summary=f"'{t.title}' cancelled: {reason}",
            actor_type=ActorType.system, project_id=project_id,
            subject_type="task", subject_id=t.id,
        )

    for t in tasks:
        if t.status != TaskStatus.queued:
            continue
        if any(slug_dead(dep) for dep in t.depends_on):
            cancel(t, "Upstream task failed")
            continue
        if not all(slug_done(dep) for dep in t.depends_on):
            continue
        # Approval gates: a non-reviewer task may not start while an upstream
        # gated artifact is unapproved. Reviewers may read pending artifacts -
        # their report informs the founder's decision.
        my_def = DEFS_BY_SLUG.get(t.agent_slug)
        if my_def is not None and not my_def.reviewer:
            gated = False
            for dep in t.depends_on:
                dep_def = DEFS_BY_SLUG.get(dep)
                if dep_def is None or not dep_def.requires_approval:
                    continue
                artifact = latest_artifact(dep)
                if artifact is None or artifact.review_status == ReviewStatus.pending_approval:
                    gated = True
                    break
                if artifact.review_status == ReviewStatus.rejected:
                    cancel(t, f"Founder rejected '{artifact.title}'")
                    gated = True
                    break
            if gated:
                continue
        return t
    return None


def _execute_one(db: Session, project_id: uuid.UUID, task_id: uuid.UUID, router: ModelRouter):
    task = db.get(Task, task_id)
    agent = db.get(Agent, task.agent_id)
    task_def = DEFS_BY_SLUG[task.agent_slug]

    if agent.status == AgentStatus.approved:
        transition(db, agent, AgentStatus.active, actor_type=ActorType.system, reason="run started")

    remaining = agent.budget_max_usd - _agent_spend(db, project_id, agent.slug)
    if remaining <= 0.01:
        task.status = TaskStatus.failed
        task.error = "Agent budget exhausted"
        transition(db, agent, AgentStatus.blocked, actor_type=ActorType.system,
                   reason="budget exhausted")
        return

    task.status = TaskStatus.running
    record_event(
        db, event_type="task.started", summary=f"{agent.name} started '{task.title}'",
        actor_type=ActorType.agent, actor_id=agent.id, project_id=project_id,
        subject_type="task", subject_id=task.id,
    )
    db.commit()  # make 'running' visible immediately

    spend_before = _agent_spend(db, project_id, agent.slug)
    try:
        output = execute_task_def(
            db, router, task_def=task_def, project_id=project_id,
            brief=_brief(db, project_id, task.agent_slug),
            upstream_context=_upstream_context(db, project_id, task.depends_on),
            max_cost_usd=remaining,
        )
    except Exception as exc:
        # task.error and the transition reason are client-visible (API/UI).
        # Store the exception class only - provider exception text can carry
        # API keys, URLs, and internals. Full detail goes to server logs.
        logger.exception(
            "task %s ('%s') failed for project %s", task_id, task.title, project_id
        )
        task.status = TaskStatus.failed
        task.error = f"The agent hit an error and stopped. ({type(exc).__name__})"
        task.cost_used_usd = _agent_spend(db, project_id, agent.slug) - spend_before
        transition(db, agent, AgentStatus.blocked, actor_type=ActorType.system,
                   reason=f"task failed: {type(exc).__name__}")
        return

    task.cost_used_usd = _agent_spend(db, project_id, agent.slug) - spend_before
    last_call = db.scalar(
        select(CostEvent)
        .where(CostEvent.project_id == project_id, CostEvent.agent_slug == agent.slug)
        .order_by(CostEvent.created_at.desc())
    )
    version = 1 + (
        db.scalar(
            select(func.max(Artifact.version)).where(
                Artifact.project_id == project_id,
                Artifact.artifact_type == task_def.artifact_type,
            )
        )
        or 0
    )
    artifact = Artifact(
        project_id=project_id,
        task_id=task.id,
        agent_id=agent.id,
        agent_slug=agent.slug,
        artifact_type=task_def.artifact_type,
        title=f"{task_def.artifact_title} v{version}",
        content=output.model_dump(),
        version=version,
        review_status=(
            ReviewStatus.pending_approval.value
            if task_def.requires_approval
            else ReviewStatus.unreviewed.value
        ),
        model_used=last_call.model if last_call else "",
        cost_usd=round(task.cost_used_usd, 4),
    )
    db.add(artifact)
    task.status = TaskStatus.done
    db.flush()

    if task_def.requires_approval:
        db.add(ApprovalRequest(
            project_id=project_id,
            subject_type="artifact",
            subject_id=artifact.id,
            requested_by_slug=agent.slug,
            title=f"Approve {artifact.title}",
            summary=f"{agent.name} finished '{artifact.title}'. Downstream work waits "
                    "for your approval.",
            context={"artifact_type": artifact.artifact_type},
            blocking=True,
        ))
        record_event(
            db, event_type="approval.requested",
            summary=f"Approval requested for '{artifact.title}'",
            actor_type=ActorType.agent, actor_id=agent.id, project_id=project_id,
            subject_type="artifact", subject_id=artifact.id,
        )

    content = artifact.content
    if artifact.artifact_type == "qa_report" and content.get("recommendation") == "block":
        db.add(ApprovalRequest(
            project_id=project_id, subject_type="artifact", subject_id=artifact.id,
            requested_by_slug=agent.slug,
            title="QA recommends blocking the PRD",
            summary=content.get("summary", ""),
            context={"findings": content.get("findings", [])},
            blocking=False,
        ))
    if artifact.artifact_type == "security_review":
        severe = [f for f in content.get("findings", [])
                  if f.get("severity") in ("high", "critical")]
        if severe:
            db.add(ApprovalRequest(
                project_id=project_id, subject_type="artifact", subject_id=artifact.id,
                requested_by_slug=agent.slug,
                title=f"Acknowledge {len(severe)} security finding(s)",
                summary=content.get("summary", ""),
                context={"findings": severe, "go_no_go": content.get("go_no_go")},
                blocking=False,
            ))
            record_event(
                db, event_type="security.findings",
                summary=f"Security review found {len(severe)} high/critical finding(s)",
                actor_type=ActorType.agent, actor_id=agent.id, project_id=project_id,
                subject_type="artifact", subject_id=artifact.id,
            )

    spend = _agent_spend(db, project_id, agent.slug)
    if agent.budget_max_usd > 0 and spend >= 0.8 * agent.budget_max_usd:
        record_event(
            db, event_type="budget.warning",
            summary=f"{agent.name} has used ${spend:.2f} of ${agent.budget_max_usd:.2f} (80%+)",
            actor_type=ActorType.system, project_id=project_id,
            subject_type="agent", subject_id=agent.id,
            payload={"spend_usd": round(spend, 4), "budget_usd": agent.budget_max_usd},
        )
    record_event(
        db, event_type="task.completed",
        summary=f"{agent.name} produced '{artifact.title}' (${task.cost_used_usd:.2f})",
        actor_type=ActorType.agent, actor_id=agent.id, project_id=project_id,
        subject_type="artifact", subject_id=artifact.id,
        payload={"artifact_type": artifact.artifact_type, "cost_usd": task.cost_used_usd},
    )


def _finish_agents(db: Session, project_id: uuid.UUID) -> None:
    agents = db.scalars(
        select(Agent).where(
            Agent.project_id == project_id, Agent.status == AgentStatus.active
        )
    )
    for agent in agents:
        tasks = list(db.scalars(select(Task).where(Task.agent_id == agent.id)))
        if tasks and all(t.status == TaskStatus.done for t in tasks):
            transition(db, agent, AgentStatus.completed, actor_type=ActorType.system,
                       reason="all tasks done")
