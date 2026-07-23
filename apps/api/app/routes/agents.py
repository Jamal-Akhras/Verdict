import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agents import Agent, AgentStatus
from app.models.ai import CostEvent
from app.models.core import User
from app.schemas.agent import AgentOut, StageIn
from app.services.agent_lifecycle import InvalidTransition, transition
from app.services.auth import current_user, owned, owned_project
from app.services.staffing import set_stage

router = APIRouter(tags=["agents"])

ACTIONS: dict[str, AgentStatus] = {
    "approve": AgentStatus.approved,
    "deny": AgentStatus.rejected,
    "pause": AgentStatus.paused,
    "resume": AgentStatus.active,
    "archive": AgentStatus.archived,
}


def _with_costs(db: Session, agents: list[Agent]) -> list[AgentOut]:
    if not agents:
        return []
    project_id = agents[0].project_id
    rows = db.execute(
        select(CostEvent.agent_slug, func.sum(CostEvent.cost_usd))
        .where(CostEvent.project_id == project_id)
        .group_by(CostEvent.agent_slug)
    ).all()
    costs = {slug: total for slug, total in rows}
    out = []
    for a in agents:
        item = AgentOut.model_validate(a)
        item.cost_used_usd = round(costs.get(a.slug, 0.0), 4)
        out.append(item)
    return out


@router.post("/projects/{project_id}/stage", response_model=list[AgentOut])
def choose_stage(
    project_id: uuid.UUID,
    body: StageIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentOut]:
    project = owned_project(db, user, project_id)
    set_stage(db, project, body.stage)
    agents = list(db.scalars(select(Agent).where(Agent.project_id == project_id)))
    return _with_costs(db, agents)


@router.get("/projects/{project_id}/agents", response_model=list[AgentOut])
def list_agents(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentOut]:
    owned_project(db, user, project_id)
    agents = list(
        db.scalars(
            select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)
        )
    )
    return _with_costs(db, agents)


@router.post("/agents/{agent_id}/{action}", response_model=AgentOut)
def agent_action(
    agent_id: uuid.UUID,
    action: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AgentOut:
    if action not in ACTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown action '{action}'")
    agent = owned(db, user, db.get(Agent, agent_id), "Agent")
    try:
        transition(db, agent, ACTIONS[action])
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _with_costs(db, [agent])[0]


@router.post("/projects/{project_id}/agents/approve-all", response_model=list[AgentOut])
def approve_all(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentOut]:
    owned_project(db, user, project_id)
    agents = list(
        db.scalars(
            select(Agent).where(
                Agent.project_id == project_id, Agent.status == AgentStatus.proposed
            )
        )
    )
    for agent in agents:
        transition(db, agent, AgentStatus.approved, reason="approve-all")
    all_agents = list(db.scalars(select(Agent).where(Agent.project_id == project_id)))
    return _with_costs(db, all_agents)
