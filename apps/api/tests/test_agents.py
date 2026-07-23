import json

from sqlalchemy import select

from app.agents.feasibility import run_feasibility
from app.agents.intake import run_intake
from app.models.ai import CostEvent
from app.models.core import Project, User
from app.providers.router import ModelRouter
from tests.conftest import FakeProvider


def make_project(db):
    user = User(clerk_id="c", email="c@example.com")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="P")
    db.add(project)
    db.flush()
    return project


INTAKE_JSON = json.dumps({
    "normalized_brief": "A booking app for boutique gyms.",
    "target_user": "small gym owners",
    "problem": "bookings managed via WhatsApp and spreadsheets",
    "assumptions": ["gyms will pay monthly"],
    "missing_info": ["budget"],
    "follow_up_questions": ["What is your budget?"],
})

FEASIBILITY_JSON = json.dumps({
    "verdict": "validate",
    "confidence": 72,
    # full rubric: categories from the spec, weights sum to 100
    # (the FeasibilityOutput validator rejects anything else)
    "scores": [
        {"category": "customer_pain", "score": 8, "weight": 20, "reasoning": "real pain"},
        {"category": "reachable_buyer", "score": 7, "weight": 15, "reasoning": "local outreach"},
        {"category": "build_feasibility", "score": 8, "weight": 15, "reasoning": "standard CRUD"},
        {"category": "monetization_clarity", "score": 7, "weight": 15, "reasoning": "clear subs"},
        {"category": "competitive_gap", "score": 5, "weight": 10, "reasoning": "crowded top"},
        {"category": "market_size", "score": 6, "weight": 10, "reasoning": "many small gyms"},
        {"category": "founder_fit", "score": 6, "weight": 10, "reasoning": "solo-friendly"},
        {"category": "risk_compliance", "score": 7, "weight": 5, "reasoning": "standard risk"},
    ],
    "reasoning": "Crowded market; validate wedge first.",
    "mvp_scope": ["schedule", "booking page", "payments"],
    "do_not_build": ["native app"],
    "assumptions": ["gyms churn off WhatsApp"],
    "validation_plan": ["interview 10 gym owners"],
})


def test_intake_agent(db):
    project = make_project(db)
    router = ModelRouter(providers={
        "openai": FakeProvider("openai", [INTAKE_JSON]),
        "anthropic": FakeProvider("anthropic", []),
    })
    out = run_intake(db, router, project_id=project.id, raw_text="gym booking idea long enough")
    assert out.target_user == "small gym owners"
    assert len(out.follow_up_questions) <= 8
    event = db.scalar(select(CostEvent))
    assert event.agent_slug == "founder-intake"
    assert event.task_type == "intake_normalization"


def test_feasibility_agent(db):
    project = make_project(db)
    router = ModelRouter(providers={
        "openai": FakeProvider("openai", [FEASIBILITY_JSON]),
        "anthropic": FakeProvider("anthropic", []),
    })
    out = run_feasibility(
        db, router, project_id=project.id,
        brief="A booking app for boutique gyms.", assumptions=["budget unknown"],
    )
    assert out.verdict == "validate"
    assert out.weighted_total() == 69.5  # sum(score * weight / 10) for the fixture
    event = db.scalar(select(CostEvent))
    assert event.agent_slug == "feasibility-analyst"
