"""Supervision hierarchy: local workers, frontier supervisors, escalation
that climbs the chain and reaches the founder only when it must."""
import json
from collections import Counter

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.agents import Agent, AgentStatus
from app.models.ai import CostEvent, ModelCall
from app.models.approvals import ApprovalRequest, ApprovalStatus
from app.models.core import IdeaSubmission, Project, ProjectStage, ProjectStatus, User
from app.models.hierarchy import Flag, FlagStatus, ModelProfile, ModelTier, ProviderKind, ReviewRecord
from app.models.work import Artifact, Task, TaskStatus
from app.providers.base import ModelResponse
from app.providers.router import ModelRouter
from app.routes.approvals import _resolve
from app.services.agent_lifecycle import transition
from app.services.hierarchy import PresetSpec, apply_preset, validate_hierarchy
from app.services.orchestrator import _upstream_context, create_run, run_project
from app.services.staffing import set_stage
from tests.test_orchestrator import FINANCE, PRD, QA_REPORT, RESEARCH

WORKER_OUTPUTS = {
    "Market Research Agent": RESEARCH,
    "Finance/ROI Agent": FINANCE,
    "Product Agent": PRD,
    "QA Agent": QA_REPORT,
}


def review(decision: str, **kw) -> str:
    body = {"decision": decision, "summary": f"{decision} it", "feedback": "",
            "issues": [], "escalation_title": "", "escalation_detail": ""}
    body.update(kw)
    return json.dumps(body)


def triage(decision: str, **kw) -> str:
    body = {"decision": decision, "rationale": "because", "resolution": "", "question": "",
            "severity": "medium"}
    body.update(kw)
    return json.dumps(body)


class RoleFake:
    """Answers by role: worker prompts get their fixture, supervision
    prompts get whatever the test's policy function decides."""

    def __init__(self, name, on_review=None, on_triage=None):
        self.name = name
        self.on_review = on_review or (lambda task, n: review("accept"))
        self.on_triage = on_triage or (lambda task, n: triage("resolve", resolution="go"))
        self.calls: list[dict] = []
        self.seen = Counter()

    def complete(self, *, model, system_prompt, user_prompt, json_output, max_tokens,
                 json_schema=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        task = next((line[6:] for line in user_prompt.splitlines()
                     if line.startswith("Task: ")), "")
        if "Verdict Supervisor Review" in system_prompt:
            self.seen[("review", task)] += 1
            text = self.on_review(task, self.seen[("review", task)])
        elif "Verdict Escalation Triage" in system_prompt:
            self.seen[("triage", task)] += 1
            text = self.on_triage(task, self.seen[("triage", task)])
        else:
            text = next(v for k, v in WORKER_OUTPUTS.items() if k in system_prompt)
        return ModelResponse(provider=self.name, model=model, text=text,
                             tokens_in=1000, tokens_out=500, latency_ms=3)


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(clerk_id="h", email="h@example.com")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="P", status=ProjectStatus.awaiting_approval,
                          instructions="Target market is Lebanon; price in USD.")
        db.add(project)
        db.flush()
        db.add(IdeaSubmission(project_id=project.id, raw_text="gym app",
                              normalized_brief="Booking app for boutique gyms"))
        set_stage(db, project, ProjectStage.validate)  # research, finance, product, qa
        for agent in db.scalars(select(Agent)):
            transition(db, agent, AgentStatus.approved)
        local = ModelProfile(user_id=user.id, name="qwen-local", provider=ProviderKind.local,
                             model="qwen3:32b", tier=ModelTier.local)
        frontier = ModelProfile(user_id=user.id, name="sonnet-api",
                                provider=ProviderKind.anthropic, model="claude-sonnet-4-5",
                                tier=ModelTier.high, price_in=3.0, price_out=15.0)
        db.add_all([local, frontier])
        db.flush()
        db.commit()
        ids = {"project": project.id, "local": local.id, "frontier": frontier.id}
    return factory, ids


def make_router(worker: RoleFake, boss: RoleFake) -> ModelRouter:
    return ModelRouter(
        providers={},
        provider_factory=lambda p: worker if p.tier == ModelTier.local else boss,
    )


def preset(factory, ids, shape="flat"):
    with factory() as db:
        apply_preset(db, db.get(Project, ids["project"]), PresetSpec(
            shape=shape,
            worker_profile=db.get(ModelProfile, ids["local"]),
            lead_profile=db.get(ModelProfile, ids["frontier"]),
            director_profile=db.get(ModelProfile, ids["frontier"]),
        ))
        db.commit()


def run(factory, pid, router):
    with factory() as db:
        create_run(db, db.get(Project, pid))
        db.commit()
    run_project(pid, router, factory)


def task_by_slug(db, slug):
    return db.scalar(select(Task).where(Task.agent_slug == slug))


def test_local_workers_reviewed_by_frontier_supervisor(env):
    factory, ids = env
    preset(factory, ids, "flat")
    worker = RoleFake("local")
    boss = RoleFake("anthropic", on_review=lambda task, n: (
        review("revise", feedback="1. Name your sources.")
        if task == "Competitor and market scan" and n == 1 else review("accept")
    ))
    run(factory, ids["project"], make_router(worker, boss))

    with factory() as db:
        research = task_by_slug(db, "market-research")
        assert research.status == TaskStatus.done
        reviews = list(db.scalars(select(ReviewRecord).where(
            ReviewRecord.task_id == research.id).order_by(ReviewRecord.attempt)))
        assert [r.decision.value for r in reviews] == ["revise", "accept"]
        assert reviews[0].reviewed_output["memo"]  # each draft kept for the trace

        # the revision prompt carried the supervisor's feedback, fenced
        redo = [c for c in worker.calls if "sent back by your supervisor" in c["user_prompt"]]
        assert len(redo) == 1
        assert "Name your sources." in redo[0]["user_prompt"]
        assert '<team_document name="Supervisor feedback"' in redo[0]["user_prompt"]

        # founder instructions reach workers and supervisors alike
        assert all("Target market is Lebanon" in c["system_prompt"]
                   for c in worker.calls + boss.calls)

        # local work is free; only supervision costs money
        events = list(db.scalars(select(CostEvent).where(CostEvent.task_id == research.id)))
        roles = Counter(e.call_role for e in events)
        assert roles == {"work": 2, "review": 2}
        assert all(e.cost_usd == 0 for e in events if e.call_role == "work")
        assert sum(e.cost_usd for e in events) == pytest.approx(research.cost_used_usd)
        assert research.cost_used_usd > 0

        # PRD keeps its default founder gate after the supervisor accepts it
        prd = db.scalar(select(Artifact).where(Artifact.artifact_type == "prd"))
        assert prd.review_status == "pending_approval"
        assert prd.model_used == "qwen3:32b"


def test_escalation_resolved_inside_hierarchy_never_reaches_founder(env):
    factory, ids = env
    preset(factory, ids, "teams")
    worker = RoleFake("local")
    boss = RoleFake(
        "anthropic",
        on_review=lambda task, n: (
            review("escalate", escalation_title="Which currency?",
                   escalation_detail="Brief is unclear on currency")
            if task == "Pricing and break-even model" else review("accept")
        ),
        on_triage=lambda task, n: triage("resolve", resolution="Use USD per the instructions."),
    )
    run(factory, ids["project"], make_router(worker, boss))

    with factory() as db:
        flag = db.scalar(select(Flag))
        assert flag.status == FlagStatus.resolved
        assert [h["agent_name"] for h in flag.chain] == ["Strategy Lead", "Director"]
        assert flag.artifact_id is not None
        finance = task_by_slug(db, "finance-roi")
        assert finance.status == TaskStatus.done
        # no desk item for a settled escalation (only the PRD gate)
        titles = [r.title for r in db.scalars(select(ApprovalRequest))]
        assert not any("Escalated" in t for t in titles)
        # the decision travels with the artifact to downstream agents
        ctx = _upstream_context(db, ids["project"], ["finance-roi"])
        assert "Use USD per the instructions." in ctx


def test_escalation_climbs_to_founder_and_gates_downstream(env):
    factory, ids = env
    preset(factory, ids, "teams")
    worker = RoleFake("local")
    boss = RoleFake(
        "anthropic",
        on_review=lambda task, n: (
            review("escalate", escalation_title="Market may be too small",
                   escalation_detail="Only ~40 boutique gyms in target city")
            if task == "Competitor and market scan" else review("accept")
        ),
        on_triage=lambda task, n: triage(
            "escalate", question="Proceed with a 40-gym market?", severity="high"),
    )
    router = make_router(worker, boss)
    run(factory, ids["project"], router)

    with factory() as db:
        flag = db.scalar(select(Flag))
        assert flag.status == FlagStatus.raised
        assert flag.detail == "Proceed with a 40-gym market?"
        request = db.get(ApprovalRequest, flag.approval_request_id)
        assert request.blocking and request.context["flag_id"] == str(flag.id)
        assert len(request.context["chain"]) == 2
        # everything downstream of research waits on the founder
        assert task_by_slug(db, "finance-roi").status == TaskStatus.queued
        assert task_by_slug(db, "product").status == TaskStatus.queued
        _resolve(db, request.id, ApprovalStatus.approved, "Yes, it's a beachhead")
        db.commit()

    run_project(ids["project"], router, factory)
    with factory() as db:
        flag = db.scalar(select(Flag))
        assert flag.status == FlagStatus.approved
        assert flag.chain[-1]["agent_name"] == "Founder"
        assert task_by_slug(db, "finance-roi").status == TaskStatus.done


def test_revision_limit_forces_escalation(env):
    factory, ids = env
    preset(factory, ids, "flat")
    with factory() as db:
        research = db.scalar(select(Agent).where(Agent.slug == "market-research"))
        research.max_revisions = 1
        db.commit()
    worker = RoleFake("local")
    boss = RoleFake("anthropic", on_review=lambda task, n: (
        review("revise", feedback="still vague") if task == "Competitor and market scan"
        else review("accept")
    ))
    run(factory, ids["project"], make_router(worker, boss))
    with factory() as db:
        research = task_by_slug(db, "market-research")
        decisions = [r.decision.value for r in db.scalars(
            select(ReviewRecord).where(ReviewRecord.task_id == research.id)
            .order_by(ReviewRecord.attempt))]
        assert decisions == ["revise", "escalate"]
        flag = db.scalar(select(Flag))
        assert "after 2 attempts" in flag.title
        # flat preset: the Director reviewed, so the founder is next
        assert flag.status == FlagStatus.raised


def test_paused_supervisor_is_skipped(env):
    factory, ids = env
    preset(factory, ids, "teams")
    with factory() as db:
        lead = db.scalar(select(Agent).where(Agent.slug == "lead-strategy"))
        transition(db, lead, AgentStatus.paused)
        db.commit()
    worker, boss = RoleFake("local"), RoleFake("anthropic")
    run(factory, ids["project"], make_router(worker, boss))
    with factory() as db:
        research = task_by_slug(db, "market-research")
        reviewer = db.scalar(select(ReviewRecord).where(ReviewRecord.task_id == research.id))
        assert db.get(Agent, reviewer.reviewer_agent_id).slug == "director"


def test_high_risk_work_on_local_model_needs_frontier_supervisor(env):
    factory, ids = env
    with factory() as db:
        project = db.get(Project, ids["project"])
        set_stage(db, project, ProjectStage.prototype)  # adds security-review (high risk)
        sec = db.scalar(select(Agent).where(Agent.slug == "security-review"))
        sec.model_profile_id = ids["local"]
        assert any("security" in e.lower() for e in validate_hierarchy(db, project.id))

        qa = db.scalar(select(Agent).where(Agent.slug == "qa"))
        qa.model_profile_id = ids["local"]
        sec.supervisor_id = qa.id
        assert any("high-tier" in e for e in validate_hierarchy(db, project.id))

        qa.model_profile_id = ids["frontier"]
        assert validate_hierarchy(db, project.id) == []

        qa.supervisor_id = sec.id
        assert any("loops" in e for e in validate_hierarchy(db, project.id))


def test_demo_mode_runs_the_full_hierarchy(env, monkeypatch):
    """Pinned profiles resolve to the demo engine with no keys configured."""
    import app.providers.demo_provider as demo
    from app.config import settings

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(demo.time, "sleep", lambda s: None)
    factory, ids = env
    preset(factory, ids, "teams")
    with factory() as db:
        # waive the PRD's founder gate (per-agent override) to run end to end
        db.scalar(select(Agent).where(Agent.slug == "product")).requires_approval = False
        db.commit()
    run(factory, ids["project"], ModelRouter(providers={}))
    with factory() as db:
        assert {t.status for t in db.scalars(select(Task))} == {TaskStatus.done}
        assert db.scalar(select(ReviewRecord)) is not None
        assert db.scalar(select(ApprovalRequest)) is None
        assert all(c.parse_ok for c in db.scalars(select(ModelCall)))


# --- API ------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.db.session import get_db
    from app.main import app

    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(settings, "local_llm_base_url", "")
    app.dependency_overrides[get_db] = override
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _project(factory, stage=ProjectStage.validate):
    from app.services.users import get_or_create_demo_user

    with factory() as db:
        user = get_or_create_demo_user(db)
        project = Project(user_id=user.id, name="P")
        db.add(project)
        db.flush()
        set_stage(db, project, stage)
        db.commit()
        return project.id


def test_profile_api_validation(client, monkeypatch):
    from app.config import settings

    c, _ = client
    r = c.post("/model-profiles", json={"name": "q", "provider": "local", "model": "qwen3:32b"})
    assert r.status_code == 422  # no base_url anywhere
    r = c.post("/model-profiles", json={"name": "q", "provider": "local", "model": "qwen3:32b",
                                        "base_url": "http://localhost:11434/v1",
                                        "price_in": 9, "price_out": 9})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "local" and body["access"] == "local"
    assert body["price_in"] == 0  # local is free, whatever the form said

    r = c.post("/model-profiles", json={"name": "s", "provider": "anthropic",
                                        "model": "claude-sonnet-4-5"})
    assert r.json()["price_out"] == 15.0 and r.json()["tier"] == "high"
    r = c.post("/model-profiles", json={"name": "x", "provider": "openai", "model": "gpt-9"})
    assert r.status_code == 422  # unknown API model must declare prices

    r = c.post("/model-profiles", json={"name": "cc", "provider": "claude_code",
                                        "model": "--dangerously-skip-permissions"})
    assert r.status_code == 422  # flag injection via model name

    monkeypatch.setattr(settings, "allow_local_providers", False)
    r = c.post("/model-profiles", json={"name": "cc", "provider": "claude_code",
                                        "model": "opus"})
    assert r.status_code == 403
    r = c.post("/model-profiles", json={"name": "b", "provider": "local", "model": "m",
                                        "base_url": "file:///etc/passwd"})
    assert r.status_code == 422


def test_agent_config_and_preset_api(client):
    c, factory = client
    pid = _project(factory)
    local = c.post("/model-profiles", json={"name": "q", "provider": "local", "model": "q",
                                            "base_url": "http://localhost:11434/v1"}).json()
    sonnet = c.post("/model-profiles", json={"name": "s", "provider": "anthropic",
                                             "model": "claude-sonnet-4-5"}).json()
    agents = c.post(f"/projects/{pid}/hierarchy/preset", json={
        "shape": "teams", "worker_profile_id": local["id"],
        "lead_profile_id": sonnet["id"], "director_profile_id": sonnet["id"],
    }).json()
    by_slug = {a["slug"]: a for a in agents}
    assert by_slug["director"]["supervisor_id"] is None
    assert by_slug["director"]["status"] == "approved"
    assert by_slug["product"]["supervisor_id"] == by_slug["lead-product"]["id"]
    assert by_slug["lead-product"]["supervisor_id"] == by_slug["director"]["id"]

    product = by_slug["product"]["id"]
    r = c.patch(f"/agents/{product}/config", json={"instructions": "Mobile-first.",
                                                   "max_revisions": 3})
    assert r.json()["instructions"] == "Mobile-first."
    assert r.json()["supervisor_id"] == by_slug["lead-product"]["id"]  # untouched
    r = c.patch(f"/agents/{product}/config", json={"supervisor_id": None})
    assert r.json()["supervisor_id"] is None  # explicit null = founder
    r = c.patch(f"/agents/{by_slug['director']['id']}/config",
                json={"supervisor_id": by_slug["lead-product"]["id"]})
    assert r.status_code == 422  # cycle

    r = c.delete(f"/model-profiles/{local['id']}")
    assert r.status_code == 409  # in use

    r = c.patch(f"/projects/{pid}/config", json={"instructions": "Be terse."})
    assert r.json()["instructions"] == "Be terse."
    assert c.get(f"/projects/{pid}/trace").json() == {"calls": [], "reviews": [], "flags": []}


def test_trace_exposes_prompts_and_roles(env):
    from app.routes.hierarchy import project_trace

    factory, ids = env
    preset(factory, ids, "flat")
    run(factory, ids["project"], make_router(RoleFake("local"), RoleFake("anthropic")))
    with factory() as db:
        user = db.scalar(select(User))
        research = task_by_slug(db, "market-research")
        trace = project_trace(ids["project"], task_id=research.id, limit=100, db=db, user=user)
        assert [c.call_role for c in trace.calls] == ["work", "review"]
        assert "Idea brief" in trace.calls[0].user_prompt
        assert trace.calls[1].router_decision["pinned_profile"] == "sonnet-api"
        assert len(trace.reviews) == 1


# --- providers --------------------------------------------------------------------

def test_local_provider_falls_back_when_json_schema_unsupported(monkeypatch):
    import httpx

    from app.providers.local_provider import LocalProvider

    sent = []

    def fake_post(url, json, headers, timeout):
        sent.append(json["response_format"]["type"])
        req = httpx.Request("POST", url)
        if json["response_format"]["type"] == "json_schema":
            return httpx.Response(400, request=req)
        return httpx.Response(200, request=req, json={
            "choices": [{"message": {"content": '{"a": 1}'}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    resp = LocalProvider(base_url="http://localhost:11434/v1").complete(
        model="qwen3:32b", system_prompt="s", user_prompt="u", json_output=True,
        max_tokens=100, json_schema={"title": "X", "type": "object"},
    )
    assert sent == ["json_schema", "json_object"]
    assert resp.text == '{"a": 1}' and resp.tokens_in == 7


def test_claude_code_provider_keeps_user_text_out_of_argv(monkeypatch):
    import subprocess

    from app.config import settings
    from app.providers import cli_provider

    monkeypatch.setattr(settings, "claude_code_enabled", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setattr(cli_provider.shutil, "which", lambda c: "/usr/bin/claude")
    seen = {}

    def fake_run(argv, *, input, cwd, env, timeout, **kw):
        seen.update(argv=argv, input=input, env=env)
        idx = argv.index("--system-prompt-file") + 1
        with open(argv[idx], encoding="utf-8") as fh:
            seen["system"] = fh.read()
        out = {"type": "result", "is_error": False, "result": "",
               "structured_output": {"ok": True},
               "usage": {"input_tokens": 10, "output_tokens": 4}}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(out), stderr="")

    monkeypatch.setattr(cli_provider.subprocess, "run", fake_run)
    resp = cli_provider.ClaudeCodeProvider().complete(
        model="sonnet", system_prompt="SYSTEM & stuff", user_prompt="USER | text",
        json_output=True, max_tokens=10, json_schema={"type": "object"},
    )
    assert json.loads(resp.text) == {"ok": True}
    assert not any("USER" in a or "SYSTEM" in a for a in seen["argv"])
    assert seen["input"] == "USER | text" and seen["system"] == "SYSTEM & stuff"
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert "--json-schema" in seen["argv"]


def test_claude_code_on_windows_shim_puts_schema_in_prompt(monkeypatch):
    import subprocess

    from app.config import settings
    from app.providers import cli_provider

    monkeypatch.setattr(settings, "claude_code_enabled", True)
    monkeypatch.setattr(cli_provider.shutil, "which", lambda c: r"C:\npm\claude.CMD")
    seen = {}

    def fake_run(argv, *, input, **kw):
        seen.update(argv=argv, input=input)
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps({"is_error": False, "result": "{}"}), stderr="")

    monkeypatch.setattr(cli_provider.subprocess, "run", fake_run)
    cli_provider.ClaudeCodeProvider().complete(
        model="opus", system_prompt="s", user_prompt="u", json_output=True,
        max_tokens=10, json_schema={"type": "object"},
    )
    assert "--json-schema" not in seen["argv"]
    assert '{"type": "object"}' in seen["input"]


def test_cli_providers_disabled_by_default():
    from app.providers.base import ProviderError
    from app.providers.cli_provider import ClaudeCodeProvider, CodexProvider

    for provider in (ClaudeCodeProvider(), CodexProvider()):
        with pytest.raises(ProviderError, match="disabled"):
            provider.complete(model="m", system_prompt="s", user_prompt="u",
                              json_output=True, max_tokens=10)


# --- founder change requests ------------------------------------------------------

def _pending_blocking(db, contains: str) -> ApprovalRequest:
    return db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.status == ApprovalStatus.pending,
        ApprovalRequest.blocking.is_(True),
        ApprovalRequest.title.contains(contains),
    ))


def test_change_request_redoes_work_with_directions_and_rereviews(env):
    from app.services.orchestrator import request_changes

    factory, ids = env
    preset(factory, ids, "flat")
    worker, boss = RoleFake("local"), RoleFake("anthropic")
    router = make_router(worker, boss)
    run(factory, ids["project"], router)

    with factory() as db:
        request = _pending_blocking(db, "PRD")
        queued = request_changes(db, request, "Add a story for cancelling a booking.")
        assert {t.agent_slug for t in queued} == {"product", "qa"}  # QA read v1
        db.commit()
        old_prd_id = request.subject_id
    worker.calls.clear()
    boss.calls.clear()
    run_project(ids["project"], router, factory)

    with factory() as db:
        redo = [c for c in worker.calls if "Product Agent" in c["system_prompt"]]
        assert len(redo) == 1
        assert "Changes the founder requested" in redo[0]["system_prompt"]
        assert "Add a story for cancelling a booking." in redo[0]["system_prompt"]
        assert "Version the founder sent back" in redo[0]["user_prompt"]
        # the supervisor checks the new draft against the founder's directions
        assert any("Add a story for cancelling" in c["user_prompt"] for c in boss.calls)

        old = db.get(Artifact, old_prd_id)
        new = db.scalar(select(Artifact).where(Artifact.supersedes_id == old_prd_id))
        assert old.review_status == "superseded"
        assert new.version == 2 and new.review_status == "pending_approval"
        assert db.get(ApprovalRequest, request.id).status == ApprovalStatus.revise
        assert _pending_blocking(db, "PRD v2") is not None
        assert len(list(db.scalars(
            select(Artifact).where(Artifact.artifact_type == "qa_report")))) == 2
        product = db.scalar(select(Agent).where(Agent.slug == "product"))
        assert product.status in (AgentStatus.active, AgentStatus.completed)


def test_change_request_on_escalation_closes_the_flag(env):
    from app.services.orchestrator import request_changes

    factory, ids = env
    preset(factory, ids, "flat")
    boss = RoleFake("anthropic", on_review=lambda task, n: (
        review("escalate", escalation_title="Scope question", escalation_detail="?")
        if task == "Competitor and market scan" and n == 1 else review("accept")
    ))
    router = make_router(RoleFake("local"), boss)
    run(factory, ids["project"], router)
    with factory() as db:
        request = _pending_blocking(db, "Escalated")
        request_changes(db, request, "Focus on Beirut only.")
        db.commit()
    run_project(ids["project"], router, factory)
    with factory() as db:
        flag = db.scalar(select(Flag))
        assert flag.status == FlagStatus.revised
        assert flag.chain[-1] == {**flag.chain[-1], "agent_name": "Founder", "decision": "revise"}
        research = list(db.scalars(select(Task).where(Task.agent_slug == "market-research")))
        assert [t.status for t in research] == [TaskStatus.done, TaskStatus.done]
        assert task_by_slug(db, "finance-roi").status == TaskStatus.done


def test_change_request_guards(env):
    from app.services.orchestrator import ChangeRequestError, request_changes

    factory, ids = env
    preset(factory, ids, "flat")
    run(factory, ids["project"], make_router(RoleFake("local"), RoleFake("anthropic")))
    with factory() as db:
        request = _pending_blocking(db, "PRD")
        with pytest.raises(ChangeRequestError, match="what should change"):
            request_changes(db, request, "   ")
        product = db.scalar(select(Agent).where(Agent.slug == "product"))
        transition(db, product, AgentStatus.archived)
        with pytest.raises(ChangeRequestError, match="resume it first"):
            request_changes(db, request, "x")
        request.status = ApprovalStatus.approved
        with pytest.raises(ChangeRequestError, match="Already resolved"):
            request_changes(db, request, "x")
