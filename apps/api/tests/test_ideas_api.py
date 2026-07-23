import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app
from app.models import Base
from app.providers.router import ModelRouter, get_router
from tests.conftest import FakeProvider
from tests.test_agents import FEASIBILITY_JSON, INTAKE_JSON


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
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

    scripted = ModelRouter(providers={
        "openai": FakeProvider("openai", [INTAKE_JSON, FEASIBILITY_JSON]),
        "anthropic": FakeProvider("anthropic", []),
    })
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_router] = lambda: scripted
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_idea_to_report_flow(client):
    r = client.post("/ideas", json={"name": "Gym MVP", "raw_text": "a gym booking app idea"})
    assert r.status_code == 200, r.text
    intake = r.json()
    assert intake["normalized_brief"]
    pid = intake["project_id"]

    r = client.post(f"/projects/{pid}/evaluate")
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["verdict"] == "validate"
    assert report["cost_estimate"]["stages"]["evaluate"]["low_usd"] > 0

    r = client.get(f"/projects/{pid}/report")
    assert r.status_code == 200
    assert r.json()["version"] == 1

    r = client.get(f"/projects/{pid}")
    assert r.json()["status"] == "awaiting_approval"
    assert r.json()["budget_used_usd"] > 0
