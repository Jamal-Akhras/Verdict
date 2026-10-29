import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db, get_session_factory
from app.models.core import ActorType, AuditEvent, User
from app.models.work import Artifact, Task, TaskStatus
from app.providers.router import ModelRouter, get_router
from app.schemas.work import ArtifactOut, AuditEventOut, TaskOut
from app.services.audit import record_event
from app.services.auth import current_user, owned, owned_project
from app.services.limits import rate_limit
from app.services.orchestrator import INFLIGHT, RunError, create_run, run_project

router = APIRouter(tags=["work"])


@router.post(
    "/projects/{project_id}/run",
    response_model=list[TaskOut],
    dependencies=[Depends(rate_limit)],
)
def start_run(
    project_id: uuid.UUID,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    session_factory=Depends(get_session_factory),
    user: User = Depends(current_user),
) -> list[Task]:
    project = owned_project(db, user, project_id)
    try:
        tasks = create_run(db, project)
    except RunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    background.add_task(run_project, project_id, model_router, session_factory)
    return tasks


@router.post(
    "/projects/{project_id}/runs/reset",
    response_model=list[TaskOut],
    dependencies=[Depends(rate_limit)],
)
def reset_run(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Task]:
    """Escape hatch: force-fail every in-flight task so a stuck run
    can be recreated immediately (no 30-minute sweep wait). Audited."""
    owned_project(db, user, project_id)
    stuck = list(
        db.scalars(
            select(Task).where(
                Task.project_id == project_id,
                Task.status.in_(INFLIGHT),
            )
        )
    )
    for t in stuck:
        t.status = TaskStatus.failed
        t.error = "force-reset by founder"
    record_event(
        db, event_type="run.reset",
        summary=f"Run force-reset: {len(stuck)} task(s) marked failed",
        actor_type=ActorType.user, project_id=project_id,
        payload={"tasks": [t.title for t in stuck]},
    )
    db.flush()
    return stuck


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Task]:
    owned_project(db, user, project_id)
    return list(
        db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at))
    )


@router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Artifact]:
    owned_project(db, user, project_id)
    return list(
        db.scalars(
            select(Artifact).where(Artifact.project_id == project_id).order_by(Artifact.created_at)
        )
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Artifact:
    return owned(db, user, db.get(Artifact, artifact_id), "Artifact")


@router.get("/projects/{project_id}/audit", response_model=list[AuditEventOut])
def list_audit(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AuditEvent]:
    owned_project(db, user, project_id)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id == project_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(200)
        )
    )
