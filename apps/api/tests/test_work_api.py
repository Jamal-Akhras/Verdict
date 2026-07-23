"""API-level tests for run recovery (reset endpoint) and approval listing."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base
from app.models.agents import Agent, AgentStatus
from app.models.core import Project, ProjectStatus, User
from app.models.work import Task, TaskStatus


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db: Session = TestingSession()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    c = TestClient(app)
    with TestingSession() as db:
        user = User(clerk_id="demo", email="demo@verdict.local")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="P", status=ProjectStatus.active)
        db.add(project)
        db.commit()
        c.project_id = str(project.id)
    c.session_factory = TestingSession
    yield c
    app.dependency_overrides.clear()


def _seed_inflight_run(factory, project_id: str) -> None:
    with factory() as db:
        agent = Agent(
            project_id=uuid.UUID(project_id), slug="market-research",
            name="Researcher", role="research", status=AgentStatus.active,
        )
        db.add(agent)
        db.flush()
        db.add(Task(
            project_id=agent.project_id, agent_id=agent.id,
            agent_slug=agent.slug, title="Market research",
            task_type="market_research", status=TaskStatus.running,
        ))
        db.add(Task(
            project_id=agent.project_id, agent_id=agent.id,
            agent_slug=agent.slug, title="Follow-up",
            task_type="market_research", status=TaskStatus.queued,
        ))
        db.commit()


def test_reset_force_fails_queued_and_running(client):
    pid = client.project_id
    _seed_inflight_run(client.session_factory, pid)

    r = client.post(f"/projects/{pid}/runs/reset")
    assert r.status_code == 200, r.text
    reset = r.json()
    assert len(reset) == 2
    assert all(t["status"] == "failed" for t in reset)
    assert all("force-reset" in t["error"] for t in reset)

    tasks = client.get(f"/projects/{pid}/tasks").json()
    assert all(t["status"] == "failed" for t in tasks)

    # audited
    audit = client.get(f"/projects/{pid}/audit").json()
    assert any(e["event_type"] == "run.reset" for e in audit)

    # idempotent: nothing left to reset
    r = client.post(f"/projects/{pid}/runs/reset")
    assert r.status_code == 200 and r.json() == []


def test_reset_unknown_project_404(client):
    r = client.post(f"/projects/{uuid.uuid4()}/runs/reset")
    assert r.status_code == 404


def test_list_approvals_invalid_status_is_422(client):
    pid = client.project_id
    r = client.get(f"/projects/{pid}/approvals?status=bogus")
    assert r.status_code == 422
    assert "bogus" in r.json()["detail"]

    r = client.get(f"/projects/{pid}/approvals?status=pending")
    assert r.status_code == 200 and r.json() == []


def test_health_ready_answers_when_db_is_up(client):
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"
