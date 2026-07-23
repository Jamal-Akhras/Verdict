"""Deterministic cost estimator. Code, not prompts (quality rule #8).

Estimates AI spend per stage from MVP scope size. Numbers are conservative
ranges based on the per-agent budgets in the seed templates.
"""
from typing import Any

STAGE_BASE: dict[str, tuple[float, float]] = {
    "evaluate": (2.0, 5.0),
    "validate": (5.0, 15.0),
    "prototype_plan": (8.0, 25.0),
    "build_plan": (15.0, 45.0),
    "monthly_after_launch": (10.0, 60.0),
}


def estimate_costs(mvp_feature_count: int) -> dict[str, Any]:
    factor = 1.0 + max(0, mvp_feature_count - 4) * 0.15
    stages = {
        stage: {"low_usd": round(lo * factor, 2), "high_usd": round(hi * factor, 2)}
        for stage, (lo, hi) in STAGE_BASE.items()
    }
    return {
        "complexity_factor": round(factor, 2),
        "mvp_feature_count": mvp_feature_count,
        "stages": stages,
        "method": "deterministic table x complexity factor; not an LLM estimate",
    }
