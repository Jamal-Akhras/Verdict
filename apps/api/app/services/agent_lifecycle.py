"""Agent state machine. All transitions go through transition();
invalid moves raise, valid moves are audited. No other code path
may write Agent.status.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentStatus
from app.models.core import ActorType
from app.services.audit import record_event

VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.proposed: {AgentStatus.approved, AgentStatus.rejected},
    AgentStatus.approved: {AgentStatus.active, AgentStatus.paused, AgentStatus.archived},
    AgentStatus.active: {
        AgentStatus.paused, AgentStatus.blocked, AgentStatus.completed, AgentStatus.archived,
    },
    AgentStatus.paused: {AgentStatus.approved, AgentStatus.active, AgentStatus.archived},
    AgentStatus.blocked: {AgentStatus.active, AgentStatus.archived},
    AgentStatus.completed: {AgentStatus.archived},
    AgentStatus.archived: set(),
    AgentStatus.rejected: set(),
}


class InvalidTransition(Exception):
    pass


def transition(
    db: Session,
    agent: Agent,
    to: AgentStatus,
    *,
    actor_type: ActorType = ActorType.user,
    actor_id: uuid.UUID | None = None,
    reason: str = "",
) -> Agent:
    if to not in VALID_TRANSITIONS[agent.status]:
        raise InvalidTransition(f"{agent.slug}: {agent.status.value} -> {to.value} not allowed")
    from_status = agent.status
    agent.status = to
    record_event(
        db,
        event_type=f"agent.{to.value}",
        summary=f"{agent.name}: {from_status.value} -> {to.value}"
        + (f" ({reason})" if reason else ""),
        actor_type=actor_type,
        actor_id=actor_id,
        project_id=agent.project_id,
        subject_type="agent",
        subject_id=agent.id,
        payload={"from": from_status.value, "to": to.value, "reason": reason},
    )
    db.flush()
    return agent
