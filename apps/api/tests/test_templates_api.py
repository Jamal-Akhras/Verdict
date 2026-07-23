import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base
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
        project = Project(user_id=user.id, name="P", status=ProjectStatus.active)
        db.add(project)
        db.commit()
        c.project_id = str(project.id)
    yield c
    app.dependency_overrides.clear()


def test_template_gallery_lists_seeds(client):
    r = client.get("/templates")
    assert r.status_code == 200
    slugs = {t["slug"] for t in r.json()}
    assert "security-review" in slugs and len(slugs) == 9


def test_staff_from_template_and_duplicate_rejected(client):
    pid = client.project_id
    r = client.post(f"/projects/{pid}/agents/staff", json={"template_slug": "qa"})
    assert r.status_code == 200
    assert r.json()["status"] == "proposed"
    r = client.post(f"/projects/{pid}/agents/staff", json={"template_slug": "qa"})
    assert r.status_code == 409


def test_custom_agent_authority_capped(client):
    pid = client.project_id
    r = client.post(
        f"/projects/{pid}/agents/custom",
        json={
            "name": "Supabase RLS Specialist",
            "role": "Review database access policies and detect unsafe row-level security setup.",
            "team": "Quality",
            "budget_max_usd": 15,
            "risk_level": "high",
            "authority": "draft",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["authority"] == "suggest"  # draft capped for user-created agents
    assert body["status"] == "proposed"
    assert body["created_by"] == "user"
