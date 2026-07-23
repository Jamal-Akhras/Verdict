"""The zero-cost promise, verified: full product flow with no API keys."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db, get_session_factory
from app.main import app
from app.models import Base
from app.providers.demo_provider import DemoProvider
from app.providers.router import ModelRouter, get_router


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

    demo = DemoProvider()
    demo_router = ModelRouter(providers={"openai": demo, "anthropic": demo, "gemini": demo})
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_session_factory] = lambda: TestingSession
    app.dependency_overrides[get_router] = lambda: demo_router
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_product_flow_with_zero_keys(client, monkeypatch):
    monkeypatch.setattr("app.providers.demo_provider.time.sleep", lambda s: None)

    # idea -> intake
    r = client.post("/ideas", json={"name": "Gym MVP", "raw_text": "a gym booking app for boutique studios"})
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    assert "boutique gyms" in r.json()["normalized_brief"]

    # evaluate -> verdict
    r = client.post(f"/projects/{pid}/evaluate")
    assert r.status_code == 200
    assert r.json()["verdict"] == "validate"

    # stage -> team -> approve
    r = client.post(f"/projects/{pid}/stage", json={"stage": "prototype"})
    assert len(r.json()) == 7
    client.post(f"/projects/{pid}/agents/approve-all")

    # run (TestClient executes background tasks synchronously on response)
    r = client.post(f"/projects/{pid}/run")
    assert r.status_code == 200

    # paused at the PRD gate with QA report already produced
    approvals = client.get(f"/projects/{pid}/approvals?status=pending").json()
    blocking = [a for a in approvals if a["blocking"]]
    assert len(blocking) == 1 and "PRD" in blocking[0]["title"]
    types = {a["artifact_type"] for a in client.get(f"/projects/{pid}/artifacts").json()}
    assert "qa_report" in types

    # approve PRD -> tech plan gate + security findings
    client.post(f"/approvals/{blocking[0]['id']}/approve", json={"note": ""})
    approvals = client.get(f"/projects/{pid}/approvals?status=pending").json()
    blocking = [a for a in approvals if a["blocking"]]
    assert len(blocking) == 1 and "Technical plan" in blocking[0]["title"]
    assert any("security" in a["title"].lower() for a in approvals if not a["blocking"])

    # approve tech plan -> backlog lands, all tasks done
    client.post(f"/approvals/{blocking[0]['id']}/approve", json={"note": ""})
    tasks = client.get(f"/projects/{pid}/tasks").json()
    assert all(t["status"] == "done" for t in tasks)
    types = {a["artifact_type"] for a in client.get(f"/projects/{pid}/artifacts").json()}
    assert "task_backlog" in types

    # every call logged as demo provider; spend simulated but tracked
    summary = client.get(f"/projects/{pid}/costs/summary").json()
    assert summary["total_usd"] > 0
    assert all(m["provider"] == "demo" for m in summary["by_model"])
