import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.agents import AgentStatus, Authority
from app.models.core import ProjectStage


class StageIn(BaseModel):
    stage: ProjectStage


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    slug: str
    name: str
    initials: str
    team: str
    role: str
    status: AgentStatus
    authority: Authority
    risk_level: str
    budget_max_usd: float
    cost_used_usd: float = 0.0
    created_by: str
    created_at: datetime
