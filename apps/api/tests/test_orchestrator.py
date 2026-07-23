import json
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.agents import Agent, AgentStatus
from app.models.approvals import ApprovalRequest, ApprovalStatus
from app.models.base import utcnow
from app.models.core import IdeaSubmission, Project, ProjectStage, ProjectStatus, User
from app.models.work import Artifact, Task, TaskStatus
from app.providers.router import ModelRouter
from app.routes.approvals import _resolve
from app.services.agent_lifecycle import transition
from app.services.orchestrator import RunError, create_run, run_project, sweep_stale_runs
from app.services.staffing import set_stage
from tests.conftest import FakeProvider, provider_error

RESEARCH = json.dumps({
    "competitors": [{"name": "Mindbody", "description": "gym SaaS", "pricing_estimate": "$139+/mo (estimate)", "gap": "too heavy for boutiques"}],
    "demand_signals": ["gyms use WhatsApp for bookings"],
    "customer_segments": ["boutique gyms"],
    "memo": "Crowded but the low end is underserved.",
    "research_gaps": ["confirm pricing"],
})
FINANCE = json.dumps({
    "pricing_recommendation": {"model": "subscription", "price_point_usd": 49, "rationale": "below incumbents"},
    "scenarios": [{"case": "base", "monthly_revenue_usd": 490, "key_driver": "10 gyms x $49"}],
    "breakeven": {"units_needed": 3, "assumption": "$150/mo costs"},
    "cost_drivers": ["hosting"],
    "assumptions": ["churn under 5%", "figures are illustrative estimates"],
})
PRD = json.dumps({
    "overview": "Booking app for boutique gyms.",
    "user_stories": [{"title": "Book a class", "story": "As a member, I want to book, so that I attend.", "acceptance_criteria": ["slot reserved"], "priority": "P0"}],
    "non_goals": ["native app"],
    "success_metrics": ["bookings/week"],
    "open_questions": [],
})
QA_REPORT = json.dumps({
    "findings": [{"section": "user_stories", "issue": "no cancellation story", "severity": "medium"}],
    "recommendation": "pass",
    "summary": "Solid PRD, one gap.",
})
TECH = json.dumps({
    "stack": [{"layer": "frontend", "choice": "Next.js", "alternative_considered": "Vite", "justification": "SSR + ecosystem"}],
    "data_model": [{"entity": "Booking", "purpose": "a reserved slot", "key_fields": ["class_id", "member_id"]}],
    "api_surface": [{"method": "POST", "path": "/bookings", "purpose": "create booking"}],
    "security_flags": [{"component": "payments", "risk": "webhook spoofing", "mitigation": "verify signatures"}],
    "adrs": [{"decision": "Postgres", "reason": "relational fits bookings"}],
    "build_order": ["schema", "api", "ui"],
})
SECURITY = json.dumps({
    "findings": [{"category": "payments", "severity": "high", "finding": "webhook signatures unverified", "recommendation": "verify Stripe signatures"}],
    "launch_checklist": [{"item": "rate limit login", "required_before_launch": True}],
    "go_no_go": "no_go",
    "summary": "Fix webhook verification before launch.",
})
BACKLOG = json.dumps({
    "tickets": [{"id": "T1", "title": "Booking schema", "objective": "Create tables", "non_goals": ["UI"], "acceptance_criteria": ["migration applies"], "test_requirements": ["model tests"], "depends_on": [], "estimated_size": "S"}],
    "build_sequence_note": "Schema first.",
})

WORK_SLUGS = {
    "market-research", "finance-roi", "product", "qa",
    "cto-architecture", "security-review", "engineering-planner",
}


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(clerk_id="c", email="c@example.com")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="P", status=ProjectStatus.awaiting_approval)
        db.add(project)
        db.flush()
        db.add(IdeaSubmission(project_id=project.id, raw_text="gym app",
                              normalized_brief="Booking app for boutique gyms"))
        set_stage(db, project, ProjectStage.prototype)
        for agent in db.scalars(select(Agent)):
            if agent.status == AgentStatus.proposed:
                transition(db, agent, AgentStatus.approved)
        db.commit()
        pid = project.id
    return factory, pid


def scripted_router(openai_script=(), anthropic_script=()):
    return ModelRouter(providers={
        "openai": FakeProvider("openai", list(openai_script)),
        "anthropic": FakeProvider("anthropic", list(anthropic_script)),
    })


def statuses(db):
    return {t.agent_slug: t.status for t in db.scalars(select(Task))}


def run_helper(factory, pid, router):
    with factory() as db:
        project = db.get(Project, pid)
        create_run(db, project)
        db.commit()
    run_project(pid, router, factory)


def approve_pending(factory, pid, title_contains: str):
    with factory() as db:
        request = db.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.project_id == pid,
                ApprovalRequest.status == ApprovalStatus.pending,
                ApprovalRequest.blocking.is_(True),
                ApprovalRequest.title.contains(title_contains),
            )
        )
        assert request is not None, f"no pending blocking approval containing '{title_contains}'"
        _resolve(db, request.id, ApprovalStatus.approved, "ok")
        db.commit()


def test_gated_run_pauses_and_resumes_through_approvals(env):
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD, TECH, SECURITY, BACKLOG],
    )
    with factory() as db:
        tasks = create_run(db, db.get(Project, pid))
        assert len(tasks) == 7
        db.commit()

    run_project(pid, router, factory)

    # paused at the PRD gate: QA ran (reviewer), CTO + planner still queued
    with factory() as db:
        s = statuses(db)
        assert s["market-research"] == TaskStatus.done
        assert s["finance-roi"] == TaskStatus.done
        assert s["product"] == TaskStatus.done
        assert s["qa"] == TaskStatus.done
        assert s["cto-architecture"] == TaskStatus.queued
        assert s["engineering-planner"] == TaskStatus.queued
        prd = db.scalar(select(Artifact).where(Artifact.artifact_type == "prd"))
        assert prd.review_status == "pending_approval"

    approve_pending(factory, pid, "PRD")
    run_project(pid, router, factory)

    # paused at the tech plan gate: security review ran, planner still queued
    with factory() as db:
        s = statuses(db)
        assert s["cto-architecture"] == TaskStatus.done
        assert s["security-review"] == TaskStatus.done
        assert s["engineering-planner"] == TaskStatus.queued
        # high security finding auto-created a non-blocking request
        security_req = db.scalar(
            select(ApprovalRequest).where(ApprovalRequest.title.contains("security"))
        )
        assert security_req is not None and security_req.blocking is False

    approve_pending(factory, pid, "Technical plan")
    run_project(pid, router, factory)

    with factory() as db:
        s = statuses(db)
        assert all(st == TaskStatus.done for st in s.values())
        types = [a.artifact_type for a in db.scalars(select(Artifact).order_by(Artifact.created_at))]
        # QA reviews the PRD, so its report can only exist after the PRD
        assert types.index("prd") < types.index("qa_report")
        assert set(types) == {
            "research_memo", "roi_model", "prd", "qa_report",
            "tech_plan", "security_review", "task_backlog",
        }
        agents = [a for a in db.scalars(select(Agent)) if a.slug in WORK_SLUGS]
        assert all(a.status == AgentStatus.completed for a in agents)
        assert db.get(Project, pid).budget_used_usd > 0


def test_denying_prd_cancels_downstream_but_not_reviewer(env):
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD],
    )
    run_helper(factory, pid, router)

    with factory() as db:
        request = db.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.blocking.is_(True),
                ApprovalRequest.status == ApprovalStatus.pending,
            )
        )
        _resolve(db, request.id, ApprovalStatus.denied, "not the right scope")
        db.commit()
    run_project(pid, router, factory)

    with factory() as db:
        s = statuses(db)
        assert s["qa"] == TaskStatus.done  # reviewer already ran
        assert s["cto-architecture"] == TaskStatus.cancelled
        assert s["engineering-planner"] == TaskStatus.cancelled
        assert s["security-review"] == TaskStatus.cancelled
        prd = db.scalar(select(Artifact).where(Artifact.artifact_type == "prd"))
        assert prd.review_status == "rejected"


def test_failure_isolates_and_cancels_downstream(env):
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, provider_error(), provider_error()],
        anthropic_script=[provider_error(), provider_error()],
    )
    run_helper(factory, pid, router)

    with factory() as db:
        s = statuses(db)
        assert s["market-research"] == TaskStatus.done
        assert s["finance-roi"] == TaskStatus.done
        assert s["product"] == TaskStatus.failed
        for slug in ("qa", "cto-architecture", "security-review", "engineering-planner"):
            assert s[slug] == TaskStatus.cancelled
        product_agent = db.scalar(select(Agent).where(Agent.slug == "product"))
        assert product_agent.status == AgentStatus.blocked


def test_budget_exhaustion_blocks_agent(env):
    factory, pid = env
    with factory() as db:
        agent = db.scalar(select(Agent).where(Agent.slug == "market-research"))
        agent.budget_max_usd = 0.0
        db.commit()
    router = scripted_router()
    run_helper(factory, pid, router)
    with factory() as db:
        research_task = db.scalar(select(Task).where(Task.agent_slug == "market-research"))
        assert research_task.status == TaskStatus.failed
        assert "budget" in research_task.error.lower()


def test_double_run_rejected(env):
    factory, pid = env
    with factory() as db:
        project = db.get(Project, pid)
        create_run(db, project)
        db.commit()
        with pytest.raises(RunError):
            create_run(db, project)


def test_budget_warning_emitted_at_80_percent(env):
    factory, pid = env
    with factory() as db:
        agent = db.scalar(select(Agent).where(Agent.slug == "market-research"))
        agent.budget_max_usd = 0.10
        db.commit()
    # 8500 output tokens on gpt-4o ~= $0.085 -> crosses 80% of the $0.10 budget
    router = ModelRouter(providers={
        "openai": FakeProvider("openai", [RESEARCH], tokens_out=8500),
        "anthropic": FakeProvider("anthropic", []),
    })
    run_helper(factory, pid, router)
    with factory() as db:
        from app.models.core import AuditEvent
        warn = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "budget.warning"))
        assert warn is not None


def _backdate_tasks(factory, pid, minutes=45):
    """Simulate a run abandoned long ago (explicit set wins over onupdate)."""
    with factory() as db:
        for t in db.scalars(select(Task).where(Task.project_id == pid)):
            t.updated_at = utcnow() - timedelta(minutes=minutes)
        db.commit()


def test_sweep_fails_orphaned_tasks_and_project_recovers(env):
    factory, pid = env
    with factory() as db:
        tasks = create_run(db, db.get(Project, pid))
        tasks[0].status = TaskStatus.running  # process died mid-task
        db.commit()
    _backdate_tasks(factory, pid)

    with factory() as db:
        assert sweep_stale_runs(db, max_age_minutes=30) == 7
        db.commit()

    with factory() as db:
        for t in db.scalars(select(Task).where(Task.project_id == pid)):
            assert t.status == TaskStatus.failed
            assert t.error == "orphaned by process restart"
        # unbricked: a fresh run can be created again
        assert len(create_run(db, db.get(Project, pid))) == 7


def test_create_run_self_heals_bricked_project(env):
    factory, pid = env
    with factory() as db:
        tasks = create_run(db, db.get(Project, pid))
        tasks[0].status = TaskStatus.running
        db.commit()
    with factory() as db:
        with pytest.raises(RunError):  # fresh run really is in flight
            create_run(db, db.get(Project, pid))
    _backdate_tasks(factory, pid)
    with factory() as db:
        # no explicit sweep call: create_run's own sweep unbricks it
        assert len(create_run(db, db.get(Project, pid))) == 7
        db.commit()


def test_sweep_spares_run_paused_at_approval_gate(env):
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD],
    )
    run_helper(factory, pid, router)  # pauses at the PRD gate
    _backdate_tasks(factory, pid)
    with factory() as db:
        # queued tasks behind a pending blocking approval are NOT orphans
        assert sweep_stale_runs(db, max_age_minutes=30) == 0
        s = statuses(db)
        assert s["cto-architecture"] == TaskStatus.queued
        assert s["engineering-planner"] == TaskStatus.queued


def test_product_prompt_receives_approved_mvp_scope(env):
    """The wiring bug fix: product.md references 'approved MVP scope', so the
    orchestrator must actually supply the feasibility report's scope."""
    from app.models.ai import FeasibilityReport, Verdict

    factory, pid = env
    with factory() as db:
        db.add(FeasibilityReport(
            project_id=pid, version=1, verdict=Verdict.validate, confidence=72,
            scores=[],
            mvp_scope=["Class schedule page", "Member booking flow"],
            do_not_build=["Native mobile app"],
            assumptions=["Owners will switch off WhatsApp"],
        ))
        db.commit()
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD],
    )
    run_helper(factory, pid, router)  # pauses at the PRD gate

    # product routes to anthropic (see other tests); its prompt must carry the scope
    anthropic = router.providers["anthropic"]
    scoped = [c for c in anthropic.calls if "Class schedule page" in c["user_prompt"]]
    assert scoped, "product prompt never received the approved MVP scope"
    prompt = scoped[0]["user_prompt"]
    assert "Do NOT build" in prompt
    assert "Native mobile app" in prompt
    assert "Owners will switch off WhatsApp" in prompt

    # QA's scope-creep check gets it too (QA routes to openai here)
    openai = router.providers["openai"]
    assert any("Class schedule page" in c["user_prompt"] for c in openai.calls)

    # research runs without a scope block (not scope-aware)
    research_call = openai.calls[0]["user_prompt"]
    assert "Approved MVP scope" not in research_call


def test_upstream_context_is_fenced_and_readable(env):
    """Upstream artifacts arrive as <team_document> blocks with readable
    per-key text, not a mid-JSON truncation."""
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD],
    )
    run_helper(factory, pid, router)
    anthropic = router.providers["anthropic"]
    prd_prompt = anthropic.calls[0]["user_prompt"]
    assert '<team_document name="Market memo v1" author="market-research">' in prd_prompt
    assert "</team_document>" in prd_prompt
    assert "memo: Crowded but the low end is underserved." in prd_prompt
    assert "<untrusted_user_input>" in prd_prompt  # the founder brief is fenced


def test_cost_summary_rollups_match(env):
    factory, pid = env
    router = scripted_router(
        openai_script=[RESEARCH, FINANCE, QA_REPORT],
        anthropic_script=[PRD],
    )
    run_helper(factory, pid, router)
    with factory() as db:
        from app.models.ai import CostEvent
        from sqlalchemy import func
        from app.routes.costs import cost_summary
        summary = cost_summary(pid, db)
        exact = db.scalar(select(func.sum(CostEvent.cost_usd)).where(CostEvent.project_id == pid))
        assert summary["total_usd"] == pytest.approx(exact, abs=1e-4)
        assert summary["total_usd"] == pytest.approx(
            sum(a["cost_usd"] for a in summary["by_agent"]), abs=1e-3
        )
        assert {a["agent_slug"] for a in summary["by_agent"]} <= WORK_SLUGS
