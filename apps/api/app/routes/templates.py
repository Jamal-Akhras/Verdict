"""Agent Builder API: browse templates, staff agents from them, or create
custom specialist agents (capped at Suggest authority - quality rule #6)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agents import Agent, AgentStatus, AgentTemplate, Authority
from app.models.core import ActorType, User
from app.routes.agents import _with_costs
from app.schemas.agent import AgentOut
from app.services.audit import record_event
from app.services.auth import current_user, owned_project
from app.services.templates import load_seed_templates

router = APIRouter(tags=["templates"])


class TemplateOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    slug: str
    version: int
    name: str
    initials: str
    team: str
    role: str
    scope: str
    checks: list
    output_types: list
    default_budget_usd: float
    risk_level: str
    authority_default: Authority
    approval_requirement: str


class StaffIn(BaseModel):
    template_slug: str


class CustomAgentIn(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    role: str = Field(min_length=10, max_length=2000)
    team: str = "Quality"
    scope: str = ""
    checks: list[str] = Field(default_factory=list)
    budget_max_usd: float = Field(default=1.0, ge=0.1, le=25.0)
    risk_level: str = "medium"
    authority: Authority = Authority.observe


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[AgentTemplate]:
    load_seed_templates(db)
    return list(db.scalars(select(AgentTemplate).order_by(AgentTemplate.team, AgentTemplate.name)))


@router.post("/projects/{project_id}/agents/staff", response_model=AgentOut)
def staff_from_template(
    project_id: uuid.UUID,
    body: StaffIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AgentOut:
    owned_project(db, user, project_id)
    load_seed_templates(db)
    template = db.scalar(
        select(AgentTemplate)
        .where(AgentTemplate.slug == body.template_slug)
        .order_by(AgentTemplate.version.desc())
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    exists = db.scalar(
        select(Agent).where(
            Agent.project_id == project_id,
            Agent.slug == template.slug,
            Agent.status.notin_([AgentStatus.archived, AgentStatus.rejected]),
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="This agent is already on the project")
    agent = Agent(
        project_id=project_id,
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
        created_by="user",
    )
    db.add(agent)
    db.flush()
    record_event(
        db, event_type="agent.proposed",
        summary=f"{agent.name} proposed from template by founder",
        actor_type=ActorType.user, project_id=project_id,
        subject_type="agent", subject_id=agent.id,
        payload={"slug": agent.slug, "budget_usd": agent.budget_max_usd},
    )
    return _with_costs(db, [agent])[0]


@router.post("/projects/{project_id}/agents/custom", response_model=AgentOut)
def create_custom_agent(
    project_id: uuid.UUID,
    body: CustomAgentIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AgentOut:
    owned_project(db, user, project_id)
    # Governance: user-created agents may not exceed Suggest authority.
    authority = body.authority if body.authority != Authority.draft else Authority.suggest
    slug = f"custom-{uuid.uuid4().hex[:8]}"
    initials = "".join(w[0] for w in body.name.split()[:2]).upper() or "CU"
    template = AgentTemplate(
        slug=slug,
        version=1,
        name=body.name,
        initials=initials,
        team=body.team,
        role=body.role,
        scope=body.scope,
        checks=body.checks,
        output_types=["custom_report"],
        task_types=[],
        default_budget_usd=body.budget_max_usd,
        risk_level=body.risk_level,
        authority_default=authority,
        approval_requirement="founder_approval",
    )
    db.add(template)
    db.flush()
    agent = Agent(
        project_id=project_id,
        template_id=template.id,
        slug=slug,
        name=body.name,
        initials=initials,
        team=body.team,
        role=body.role,
        status=AgentStatus.proposed,
        authority=authority,
        risk_level=body.risk_level,
        budget_max_usd=body.budget_max_usd,
        created_by="user",
    )
    db.add(agent)
    db.flush()
    record_event(
        db, event_type="agent.proposed",
        summary=f"Custom agent '{agent.name}' created by founder "
        f"(authority {authority.value}, budget ${agent.budget_max_usd:.2f})",
        actor_type=ActorType.user, project_id=project_id,
        subject_type="agent", subject_id=agent.id,
        payload={"slug": slug, "custom": True},
    )
    return _with_costs(db, [agent])[0]
