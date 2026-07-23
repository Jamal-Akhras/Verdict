import uuid

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.base import INJECTION_GUARD, fence_user_input, load_prompt
from app.providers.router import ModelRouter


class IntakeOutput(BaseModel):
    normalized_brief: str
    target_user: str = "unknown"
    problem: str = "unknown"
    assumptions: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=8)


AGENT_SLUG = "founder-intake"
BUDGET_USD = 0.50


def run_intake(
    db: Session,
    router: ModelRouter,
    *,
    project_id: uuid.UUID,
    raw_text: str,
    answers: dict[str, str] | None = None,
) -> IntakeOutput:
    user_prompt = f"{INJECTION_GUARD}\n\nRaw idea:\n{fence_user_input(raw_text)}"
    if answers:
        answered = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())
        user_prompt += (
            f"\n\nThe founder answered these follow-ups:\n{fence_user_input(answered)}\n\n"
            "Incorporate the answers. Only ask NEW questions if something "
            "important is still missing."
        )
    return router.run(
        db,
        task_type="intake_normalization",
        output_schema=IntakeOutput,
        system_prompt=load_prompt("intake"),
        user_prompt=user_prompt,
        risk_level="low",
        max_cost_usd=BUDGET_USD,
        project_id=project_id,
        agent_slug=AGENT_SLUG,
    )
