"""Migration #1 smoke tests: models create, audit writer is append-only in shape."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Base, IdeaSubmission, Project, User
from app.models.core import ActorType
from app.services import audit


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_models_roundtrip(db: Session):
    user = User(clerk_id="clerk_1", email="j@example.com", name="Jamal")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="Gym Booking MVP")
    db.add(project)
    db.flush()
    idea = IdeaSubmission(project_id=project.id, raw_text="An app for gym class bookings")
    db.add(idea)
    db.commit()

    assert db.scalar(select(Project)).name == "Gym Booking MVP"
    assert db.scalar(select(IdeaSubmission)).project_id == project.id


def test_audit_event_recorded(db: Session):
    user = User(clerk_id="clerk_1", email="j@example.com")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="Demo")
    db.add(project)
    db.flush()

    event = audit.record_event(
        db,
        event_type="project.created",
        summary="Project 'Demo' created",
        actor_type=ActorType.user,
        actor_id=user.id,
        project_id=project.id,
        subject_type="project",
        subject_id=project.id,
        payload={"status": "intake"},
    )
    db.commit()

    stored = db.get(AuditEvent, event.id)
    assert stored is not None
    assert stored.event_type == "project.created"
    assert stored.payload == {"status": "intake"}


def test_audit_module_has_no_mutation_api():
    assert not hasattr(audit, "update_event")
    assert not hasattr(audit, "delete_event")
