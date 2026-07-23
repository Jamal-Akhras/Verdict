"""Public share links: owner mints, world reads sanitized verdict, tokens
are idempotent and unguessable, and auth still guards everything else."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Base
from app.models.ai import FeasibilityReport, Verdict
from app.models.core import Project, ProjectStatus, User


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
        project = Project(user_id=user.id, name="Gym MVP", status=ProjectStatus.awaiting_approval)
        db.add(project)
        db.flush()
        db.add(FeasibilityReport(
            project_id=project.id, version=1, verdict=Verdict.validate, confidence=72,
            scores=[{"category": "customer_pain", "score": 8, "weight": 20, "reasoning": "r"}],
            mvp_scope=["schedule"], do_not_build=["native app"], assumptions=[],
            validation_plan=[], reasoning="Solid wedge.",
        ))
        db.commit()
        c.project_id = str(project.id)
    yield c
    app.dependency_overrides.clear()


def test_share_mint_idempotent_and_public_read(client):
    r1 = client.post(f"/projects/{client.project_id}/report/share")
    assert r1.status_code == 200
    token = r1.json()["token"]
    assert len(token) >= 24
    # idempotent
    r2 = client.post(f"/projects/{client.project_id}/report/share")
    assert r2.json()["token"] == token

    r = client.get(f"/share/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "validate"
    assert body["project_name"] == "Gym MVP"
    # sanitized surface only
    assert set(body) == {
        "project_name", "verdict", "confidence", "scores", "reasoning",
        "mvp_scope", "do_not_build", "created_at",
    }


def test_share_read_is_public_even_with_auth_enabled(client, monkeypatch):
    token = client.post(f"/projects/{client.project_id}/report/share").json()["token"]
    monkeypatch.setattr(settings, "api_auth_token", "sekrit")
    # protected route now requires auth...
    assert client.get(f"/projects/{client.project_id}/report").status_code == 401
    # ...but the share page stays open
    assert client.get(f"/share/{token}").status_code == 200


def test_bad_or_short_tokens_404(client):
    assert client.get("/share/nonexistent-token-xyz").status_code == 404
    assert client.get("/share/short").status_code == 404


def test_share_revocation(client):
    token = client.post(f"/projects/{client.project_id}/report/share").json()["token"]
    assert client.get(f"/share/{token}").status_code == 200
    r = client.request("DELETE", f"/projects/{client.project_id}/report/share")
    assert r.status_code == 200 and r.json()["revoked"] is True
    # the old link is dead
    assert client.get(f"/share/{token}").status_code == 404
    # a fresh share mints a NEW token
    new_token = client.post(f"/projects/{client.project_id}/report/share").json()["token"]
    assert new_token != token


def test_share_read_sets_cache_headers(client):
    token = client.post(f"/projects/{client.project_id}/report/share").json()["token"]
    r = client.get(f"/share/{token}")
    assert "max-age" in r.headers.get("cache-control", "")
