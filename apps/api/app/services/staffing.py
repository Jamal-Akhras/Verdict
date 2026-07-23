"""Stage gate: turn a founder's stage decision into a proposed agent team."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentStatus, AgentTemplate
from app.models.core import ActorType, Project, ProjectStage, ProjectStatus
from app.services.audit import record_event
from app.services.templates import load_seed_templates

# Which template slugs staff each buildable stage.
STAGE_TEAMS: dict[ProjectStage, list[str]] = {
    ProjectStage.validate: ["market-research", "finance-roi", "product", "qa"],
    ProjectStage.prototype: [
        "market-research", "finance-roi", "product",
        "cto-architecture", "engineering-planner", "qa", "security-review",
    ],
    ProjectStage.build: [
        "market-research", "finance-roi", "product",
        "cto-architecture", "engineering-planner", "qa", "security-review",
    ],
}

TERMINAL_STATUS: dict[ProjectStage, ProjectStatus] = {
    ProjectStage.kill: ProjectStatus.archived,
    ProjectStage.park: ProjectStatus.parked,
    ProjectStage.research: ProjectStatus.awaiting_approval,
}


def set_stage(
    db: Session, project: Project, stage: ProjectStage, *, actor_id: uuid.UUID | None = None
) -> list[Agent]:
    """Set the project stage. For buildable stages, propose an agent team
    (idempotent: agents are only proposed once per slug per project)."""
    project.stage = stage
    record_event(
        db, event_type="project.stage_set", summary=f"Stage set to '{stage.value}'",
        actor_type=ActorType.user, actor_id=actor_id, project_id=project.id,
        subject_type="project", subject_id=project.id, payload={"stage": stage.value},
    )

    if stage in TERMINAL_STATUS:
        project.status = TERMINAL_STATUS[stage]
        db.flush()
        return []

    load_seed_templates(db)
    project.status = ProjectStatus.active
    existing = set(
        db.scalars(select(Agent.slug).where(Agent.project_id == project.id))
    )
    created: list[Agent] = []
    for slug in STAGE_TEAMS.get(stage, []):
        if slug in existing:
            continue
        template = db.scalar(
            select(AgentTemplate)
            .where(AgentTemplate.slug == slug)
            .order_by(AgentTemplate.version.desc())
        )
        if template is None:
            continue
        agent = Agent(
            project_id=project.id,
            template_id=template.id,
            slug=template.slug,
            name=template.name,
            initials=template.initials,
            team=template.team,
            role=template.role,
            status=AgentStatus.proposed,
            authority=template.authority_default,
            risk_level=template.risk_level,
            budget_max_usd=template.default_budget_usd,
            created_by="system",
        )
        db.add(agent)
        created.append(agent)
    db.flush()
    for agent in created:
        record_event(
            db, event_type="agent.proposed",
            summary=f"{agent.name} proposed for stage '{stage.value}' "
            f"(budget ${agent.budget_max_usd:.2f}, authority {agent.authority.value})",
            actor_type=ActorType.system, project_id=project.id,
            subject_type="agent", subject_id=agent.id,
            payload={"slug": agent.slug, "budget_usd": agent.budget_max_usd},
        )
    return created
