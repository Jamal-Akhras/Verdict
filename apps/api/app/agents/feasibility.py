import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.agents.base import INJECTION_GUARD, fence_user_input, load_prompt
from app.providers.router import ModelRouter

# The rubric spec (prompts/feasibility.md). Deterministic validator input:
# every returned category must come from this set.
RUBRIC_CATEGORIES = {
    "customer_pain",
    "reachable_buyer",
    "build_feasibility",
    "monetization_clarity",
    "competitive_gap",
    "market_size",
    "founder_fit",
    "risk_compliance",
}


class RubricScore(BaseModel):
    category: str
    score: int = Field(ge=0, le=10)
    weight: int
    reasoning: str


class FeasibilityOutput(BaseModel):
    verdict: Literal["kill", "park", "research", "validate", "prototype", "build"]
    confidence: int = Field(ge=0, le=100)
    scores: list[RubricScore]
    reasoning: str
    mvp_scope: list[str]
    do_not_build: list[str]
    assumptions: list[str]
    validation_plan: list[str]

    @model_validator(mode="after")
    def check_rubric(self) -> "FeasibilityOutput":
        """Deterministic quality gates; a violation triggers the router's
        repair attempt via the normal ValidationError path."""
        total_weight = sum(s.weight for s in self.scores)
        if not 95 <= total_weight <= 105:
            raise ValueError(
                f"rubric weights must sum to 100 (got {total_weight}); "
                "use the weights from the rubric spec"
            )
        unknown = {s.category for s in self.scores} - RUBRIC_CATEGORIES
        if unknown:
            raise ValueError(
                f"unknown rubric categories {sorted(unknown)}; "
                f"allowed categories: {sorted(RUBRIC_CATEGORIES)}"
            )
        return self

    def weighted_total(self) -> float:
        return sum(s.score * s.weight / 10 for s in self.scores)


AGENT_SLUG = "feasibility-analyst"
BUDGET_USD = 1.50


def run_feasibility(
    db: Session,
    router: ModelRouter,
    *,
    project_id: uuid.UUID,
    brief: str,
    assumptions: list[str],
    answers_summary: str = "",
) -> FeasibilityOutput:
    assumptions_text = "\n".join(f"- {a}" for a in assumptions)
    user_prompt = (
        f"{INJECTION_GUARD}\n\n"
        f"Idea brief:\n{fence_user_input(brief)}\n\n"
        f"Known assumptions:\n{fence_user_input(assumptions_text)}"
    )
    if answers_summary:
        user_prompt += f"\n\nFounder-provided details:\n{fence_user_input(answers_summary)}"
    return router.run(
        db,
        task_type="feasibility_scoring",
        output_schema=FeasibilityOutput,
        system_prompt=load_prompt("feasibility"),
        user_prompt=user_prompt,
        risk_level="medium",
        max_cost_usd=BUDGET_USD,
        max_tokens=6000,
        project_id=project_id,
        agent_slug=AGENT_SLUG,
    )
