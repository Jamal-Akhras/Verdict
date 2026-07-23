import pytest
from sqlalchemy import select

from app.models.agents import Agent, AgentStatus
from app.models.core import AuditEvent, Project, ProjectStage, ProjectStatus, User
from app.services.agent_lifecycle import InvalidTransition, transition
from app.services.staffing import set_stage
from app.services.templates import load_seed_templates


def make_project(db):
    user = User(clerk_id="c", email="c@example.com")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="P", status=ProjectStatus.awaiting_approval)
    db.add(project)
    db.flush()
    return project


def test_seed_templates_idempotent(db):
    n1 = load_seed_templates(db)
    n2 = load_seed_templates(db)
    assert n1 == 9 and n2 == 0


def test_prototype_stage_creates_proposed_team(db):
    project = make_project(db)
    created = set_stage(db, project, ProjectStage.prototype)
    assert len(created) == 7
    assert all(a.status == AgentStatus.proposed for a in created)
    assert project.status == ProjectStatus.active
    # idempotent: choosing the stage again proposes nothing new
    assert set_stage(db, project, ProjectStage.prototype) == []
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "agent.proposed")
    ).all()
    assert len(events) == 7


def test_kill_stage_archives_without_team(db):
    project = make_project(db)
    created = set_stage(db, project, ProjectStage.kill)
    assert created == []
    assert project.status == ProjectStatus.archived
    assert db.scalars(select(Agent)).all() == []


def test_valid_transition_is_audited(db):
    project = make_project(db)
    [agent, *_] = set_stage(db, project, ProjectStage.validate)
    transition(db, agent, AgentStatus.approved)
    assert agent.status == AgentStatus.approved
    event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "agent.approved"))
    assert event is not None
    assert event.payload["from"] == "proposed"


def test_invalid_transition_rejected(db):
    project = make_project(db)
    [agent, *_] = set_stage(db, project, ProjectStage.validate)
    with pytest.raises(InvalidTransition):
        transition(db, agent, AgentStatus.completed)  # proposed -> completed illegal
    assert agent.status == AgentStatus.proposed


def test_archived_is_terminal(db):
    project = make_project(db)
    [agent, *_] = set_stage(db, project, ProjectStage.validate)
    transition(db, agent, AgentStatus.approved)
    transition(db, agent, AgentStatus.archived)
    with pytest.raises(InvalidTransition):
        transition(db, agent, AgentStatus.active)
