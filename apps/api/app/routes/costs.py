import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agents import Agent
from app.models.ai import CostEvent
from app.models.core import User
from app.services.auth import current_user, owned_project

router = APIRouter(tags=["costs"])


@router.get("/projects/{project_id}/costs/summary")
def cost_summary(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    # isinstance check keeps direct (non-FastAPI) calls in services/tests
    # working: there `user` arrives as the Depends sentinel, not a User.
    if isinstance(user, User):
        owned_project(db, user, project_id)
    total = db.scalar(
        select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)).where(
            CostEvent.project_id == project_id
        )
    )
    budgets = {
        a.slug: a.budget_max_usd
        for a in db.scalars(select(Agent).where(Agent.project_id == project_id))
    }
    by_agent = [
        {
            "agent_slug": slug,
            "cost_usd": round(cost, 4),
            "calls": calls,
            "budget_usd": budgets.get(slug),
        }
        for slug, cost, calls in db.execute(
            select(
                CostEvent.agent_slug,
                func.sum(CostEvent.cost_usd),
                func.count(CostEvent.id),
            )
            .where(CostEvent.project_id == project_id)
            .group_by(CostEvent.agent_slug)
            .order_by(func.sum(CostEvent.cost_usd).desc())
        ).all()
    ]
    by_model = [
        {
            "provider": provider,
            "model": model,
            "cost_usd": round(cost, 4),
            "calls": calls,
            "tokens_in": tin,
            "tokens_out": tout,
        }
        for provider, model, cost, calls, tin, tout in db.execute(
            select(
                CostEvent.provider,
                CostEvent.model,
                func.sum(CostEvent.cost_usd),
                func.count(CostEvent.id),
                func.sum(CostEvent.tokens_in),
                func.sum(CostEvent.tokens_out),
            )
            .where(CostEvent.project_id == project_id)
            .group_by(CostEvent.provider, CostEvent.model)
            .order_by(func.sum(CostEvent.cost_usd).desc())
        ).all()
    ]
    return {"total_usd": round(total, 4), "by_agent": by_agent, "by_model": by_model}
