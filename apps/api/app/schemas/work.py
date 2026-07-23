import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.work import TaskStatus


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    agent_id: uuid.UUID
    agent_slug: str
    title: str
    task_type: str
    status: TaskStatus
    depends_on: list[Any]
    cost_used_usd: float
    error: str
    created_at: datetime
    updated_at: datetime


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID
    agent_id: uuid.UUID
    agent_slug: str
    artifact_type: str
    title: str
    content: dict[str, Any]
    version: int
    review_status: str
    model_used: str
    cost_usd: float
    created_at: datetime


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_type: str
    event_type: str
    summary: str
    subject_type: str | None
    subject_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    requested_by_slug: str
    title: str
    summary: str
    context: dict[str, Any]
    blocking: bool
    status: str
    resolution_note: str
    created_at: datetime
