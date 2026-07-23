import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.models.ai import CostEvent, ModelCall
from app.models.core import Project, User
from app.providers.router import ModelRouter, RoutingError
from tests.conftest import FakeProvider, ok_json, provider_error


class Out(BaseModel):
    answer: str


def make_router(openai_script, anthropic_script=()):
    return ModelRouter(
        providers={
            "openai": FakeProvider("openai", openai_script),
            "anthropic": FakeProvider("anthropic", anthropic_script),
        }
    )


def make_project(db):
    user = User(clerk_id="c", email="c@example.com")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="P")
    db.add(project)
    db.flush()
    return project


def test_routes_by_task_type_and_logs_cost(db):
    project = make_project(db)
    r = make_router([ok_json({"answer": "hi"})])
    out = r.run(
        db, task_type="intake_normalization", output_schema=Out,
        system_prompt="s", user_prompt="u", project_id=project.id, agent_slug="a1",
    )
    assert out.answer == "hi"
    event = db.scalar(select(CostEvent))
    assert event.model == "gpt-4o-mini" and event.cost_usd > 0
    call = db.scalar(select(ModelCall))
    assert call.parse_ok and call.router_decision["chosen"] == "gpt-4o-mini"
    assert db.get(Project, project.id).budget_used_usd == pytest.approx(event.cost_usd)


def test_fallback_to_next_provider_on_error(db):
    project = make_project(db)
    r = make_router([provider_error()], [ok_json({"answer": "fallback"})])
    out = r.run(
        db, task_type="intake_normalization", output_schema=Out,
        system_prompt="s", user_prompt="u", project_id=project.id,
    )
    assert out.answer == "fallback"
    event = db.scalar(select(CostEvent))
    assert event.provider == "anthropic"


def test_parse_failure_logged_then_repaired(db):
    project = make_project(db)
    r = make_router(["not json at all", ok_json({"answer": "fixed"})])
    out = r.run(
        db, task_type="intake_normalization", output_schema=Out,
        system_prompt="s", user_prompt="u", project_id=project.id,
    )
    assert out.answer == "fixed"
    events = db.scalars(select(CostEvent)).all()
    assert len(events) == 2  # failed attempt logged too - no untracked spend
    calls = db.scalars(select(ModelCall).order_by(ModelCall.created_at)).all()
    assert [c.parse_ok for c in calls] == [False, True]


def test_high_risk_requires_high_tier(db):
    project = make_project(db)
    r = make_router([ok_json({"answer": "x"})])
    r.run(
        db, task_type="feasibility_scoring", output_schema=Out,
        system_prompt="s", user_prompt="u", risk_level="high",
        max_cost_usd=1.0, project_id=project.id,
    )
    event = db.scalar(select(CostEvent))
    assert event.model == "gpt-4o"  # high tier


def test_cost_ceiling_skips_expensive_candidates(db):
    # prd_generation prefers claude-sonnet ($0.045 est here) then gpt-4o ($0.035).
    # Ceiling $0.04 must skip sonnet and route to gpt-4o.
    project = make_project(db)
    r = make_router([ok_json({"answer": "cheap"})], [])
    out = r.run(
        db, task_type="prd_generation", output_schema=Out,
        system_prompt="s" * 40000, user_prompt="u", max_cost_usd=0.04,
        max_tokens=1000, project_id=project.id,
    )
    assert out.answer == "cheap"
    event = db.scalar(select(CostEvent))
    assert event.model == "gpt-4o"


def test_all_candidates_fail_raises(db):
    project = make_project(db)
    r = make_router([provider_error()], [provider_error()])
    with pytest.raises(RoutingError):
        r.run(
            db, task_type="intake_normalization", output_schema=Out,
            system_prompt="s", user_prompt="u", project_id=project.id,
        )


def test_unknown_task_type_raises(db):
    r = make_router([])
    with pytest.raises(RoutingError):
        r.run(db, task_type="nope", output_schema=Out, system_prompt="s", user_prompt="u")
