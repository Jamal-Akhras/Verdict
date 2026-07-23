import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.core import ProjectStage, ProjectStatus


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: ProjectStatus
    stage: ProjectStage
    budget_total_usd: float
    budget_used_usd: float
    created_at: datetime
