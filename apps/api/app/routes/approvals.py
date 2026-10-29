import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db, get_session_factory
from app.models.approvals import ApprovalRequest, ApprovalStatus
from app.models.base import utcnow
from app.models.core import ActorType, User
from app.models.hierarchy import Flag, FlagStatus
from app.models.work import Artifact, ReviewStatus
from app.providers.router import ModelRouter, get_router
from app.schemas.work import ApprovalOut
from app.services.audit import record_event
from app.services.auth import current_user, owned, owned_project
from app.services.orchestrator import ChangeRequestError, request_changes, run_project

router = APIRouter(tags=["approvals"])


class ResolveIn(BaseModel):
    note: str = ""


@router.get("/projects/{project_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    project_id: uuid.UUID,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ApprovalRequest]:
    owned_project(db, user, project_id)
    q = select(ApprovalRequest).where(ApprovalRequest.project_id == project_id)
    if status:
        try:
            parsed = ApprovalStatus(status)
        except ValueError as exc:
            valid = ", ".join(s.value for s in ApprovalStatus)
            raise HTTPException(
                status_code=422, detail=f"Invalid status '{status}'; expected one of: {valid}"
            ) from exc
        q = q.where(ApprovalRequest.status == parsed)
    return list(db.scalars(q.order_by(ApprovalRequest.created_at.desc())))


def _resolve(
    db: Session,
    request_id: uuid.UUID,
    decision: ApprovalStatus,
    note: str,
    user: User | None = None,
) -> ApprovalRequest:
    request = db.get(ApprovalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if user is not None:
        owned(db, user, request, "Approval request")
    if request.status != ApprovalStatus.pending:
        raise HTTPException(status_code=409, detail="Already resolved")
    request.status = decision
    request.resolution_note = note
    flag_id = (request.context or {}).get("flag_id")
    if flag_id:
        # An escalation that climbed the hierarchy: the founder's answer
        # closes the flag's chain.
        flag = db.get(Flag, uuid.UUID(flag_id))
        if flag is not None:
            flag.status = (
                FlagStatus.approved if decision == ApprovalStatus.approved
                else FlagStatus.denied
            )
            flag.resolution = note
            flag.chain = [*flag.chain, {
                "agent_id": None, "agent_name": "Founder", "model": "human",
                "decision": decision.value, "rationale": note, "at": utcnow().isoformat(),
            }]
    if request.subject_type == "artifact" and request.blocking:
        artifact = db.get(Artifact, request.subject_id)
        if artifact is not None:
            artifact.review_status = (
                ReviewStatus.approved.value
                if decision == ApprovalStatus.approved
                else ReviewStatus.rejected.value
            )
    record_event(
        db, event_type=f"approval.{decision.value}",
        summary=f"'{request.title}' {decision.value}" + (f" - {note}" if note else ""),
        actor_type=ActorType.user, project_id=request.project_id,
        subject_type=request.subject_type, subject_id=request.subject_id,
        payload={"note": note, "blocking": request.blocking},
    )
    db.flush()
    return request


@router.post("/approvals/{request_id}/approve", response_model=ApprovalOut)
def approve(
    request_id: uuid.UUID,
    body: ResolveIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    session_factory=Depends(get_session_factory),
    user: User = Depends(current_user),
) -> ApprovalRequest:
    request = _resolve(db, request_id, ApprovalStatus.approved, body.note, user=user)
    db.commit()
    if request.blocking:
        background.add_task(run_project, request.project_id, model_router, session_factory)
    return request


@router.post("/approvals/{request_id}/revise", response_model=ApprovalOut)
def request_revision(
    request_id: uuid.UUID,
    body: ResolveIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    session_factory=Depends(get_session_factory),
    user: User = Depends(current_user),
) -> ApprovalRequest:
    """Send gated work back with directions instead of approving or
    rejecting it outright; the run resumes with the agent redoing it."""
    request = owned(db, user, db.get(ApprovalRequest, request_id), "Approval request")
    try:
        request_changes(db, request, body.note, actor_id=user.id)
    except ChangeRequestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    background.add_task(run_project, request.project_id, model_router, session_factory)
    return request


@router.post("/approvals/{request_id}/deny", response_model=ApprovalOut)
def deny(
    request_id: uuid.UUID,
    body: ResolveIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    session_factory=Depends(get_session_factory),
    user: User = Depends(current_user),
) -> ApprovalRequest:
    request = _resolve(db, request_id, ApprovalStatus.denied, body.note, user=user)
    db.commit()
    if request.blocking:
        # resume so downstream tasks get cancelled cleanly and agents finish
        background.add_task(run_project, request.project_id, model_router, session_factory)
    return request
