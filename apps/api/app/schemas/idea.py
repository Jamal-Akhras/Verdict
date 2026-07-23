import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IdeaIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=10)


class AnswersIn(BaseModel):
    answers: dict[str, str]


class IntakeOut(BaseModel):
    project_id: uuid.UUID
    submission_id: uuid.UUID
    normalized_brief: str
    target_user: str
    problem: str
    assumptions: list[str]
    missing_info: list[str]
    follow_up_questions: list[str]


class FeasibilityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    verdict: str
    confidence: int
    scores: list[Any]
    mvp_scope: list[Any]
    do_not_build: list[Any]
    assumptions: list[Any]
    validation_plan: list[Any]
    reasoning: str
    cost_estimate: dict[str, Any]
    created_at: datetime
