"""Append-only audit writer.

Every state transition in the system goes through record_event().
There is intentionally no update or delete function in this module.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.core import ActorType, AuditEvent


def record_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor_type: ActorType = ActorType.system,
    actor_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        summary=summary,
        actor_type=actor_type,
        actor_id=actor_id,
        project_id=project_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload or {},
    )
    db.add(event)
    db.flush()  # assign id; commit is the caller's transaction boundary
    return event
