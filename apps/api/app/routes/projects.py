import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.core import ActorType, Project, ProjectStatus, User
from app.schemas.project import ProjectOut
from app.services.audit import record_event
from app.services.auth import current_user, owned_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(Project.created_at.desc())
        )
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    return owned_project(db, user, project_id)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    project = owned_project(db, user, project_id)
    project.status = ProjectStatus.archived
    record_event(
        db,
        event_type="project.archived",
        summary=f"Project '{project.name}' archived",
        actor_type=ActorType.user,
        actor_id=user.id,
        project_id=project.id,
        subject_type="project",
        subject_id=project.id,
    )
    return project
