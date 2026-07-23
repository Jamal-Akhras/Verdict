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
        project = Project(user_id=user.id, name="P", status=ProjectStatus.awaiting_approval)
        db.add(project)
        db.commit()
        c.project_id = str(project.id)
    yield c
    app.dependency_overrides.clear()


def test_stage_to_team_to_approval_flow(client):
    pid = client.project_id
    r = client.post(f"/projects/{pid}/stage", json={"stage": "prototype"})
    assert r.status_code == 200, r.text
    agents = r.json()
    assert len(agents) == 7
    assert all(a["status"] == "proposed" for a in agents)

    r = client.post(f"/projects/{pid}/agents/approve-all")
    assert r.status_code == 200
    assert all(a["status"] == "approved" for a in r.json())

    first = r.json()[0]
    r = client.post(f"/agents/{first['id']}/pause")
    assert r.status_code == 200 and r.json()["status"] == "paused"

    # invalid transition -> 409
    r = client.post(f"/agents/{first['id']}/deny")
    assert r.status_code == 409

    r = client.get(f"/projects/{pid}/agents")
    assert r.status_code == 200
    assert len(r.json()) == 7
