import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.feasibility import run_feasibility
from app.agents.intake import run_intake
from app.db.session import get_db
from app.models.ai import FeasibilityReport
from app.models.core import ActorType, IdeaSubmission, Project, ProjectStatus, User
from app.providers.router import ModelRouter, get_router
from app.schemas.idea import AnswersIn, FeasibilityReportOut, IdeaIn, IntakeOut
from app.services.audit import record_event
from app.services.auth import current_user, owned_project
from app.services.cost_estimator import estimate_costs
from app.services.limits import check_daily_spend, rate_limit

router = APIRouter(tags=["ideas"])


@router.post("/ideas", response_model=IntakeOut, dependencies=[Depends(rate_limit)])
def submit_idea(
    body: IdeaIn,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    user: User = Depends(current_user),
) -> IntakeOut:
    check_daily_spend(db)  # cost-bomb defense: these routes trigger model calls
    project = Project(user_id=user.id, name=body.name, status=ProjectStatus.intake)
    db.add(project)
    db.flush()
    record_event(
        db, event_type="project.created", summary=f"Project '{project.name}' created from idea",
        actor_type=ActorType.user, actor_id=user.id, project_id=project.id,
        subject_type="project", subject_id=project.id,
    )

    intake = run_intake(db, model_router, project_id=project.id, raw_text=body.raw_text)

    submission = IdeaSubmission(
        project_id=project.id,
        raw_text=body.raw_text,
        normalized_brief=intake.normalized_brief,
        missing_info=intake.missing_info,
    )
    db.add(submission)
    db.flush()
    record_event(
        db, event_type="intake.completed",
        summary="Intake Agent normalized the idea and produced follow-up questions",
        actor_type=ActorType.agent, project_id=project.id,
        subject_type="idea_submission", subject_id=submission.id,
        payload={"questions": len(intake.follow_up_questions)},
    )
    return IntakeOut(
        project_id=project.id, submission_id=submission.id, **intake.model_dump()
    )


@router.post(
    "/projects/{project_id}/answers",
    response_model=IntakeOut,
    dependencies=[Depends(rate_limit)],
)
def submit_answers(
    project_id: uuid.UUID,
    body: AnswersIn,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    user: User = Depends(current_user),
) -> IntakeOut:
    check_daily_spend(db)
    project = owned_project(db, user, project_id)
    prev = db.scalar(
        select(IdeaSubmission)
        .where(IdeaSubmission.project_id == project_id)
        .order_by(IdeaSubmission.created_at.desc())
    )
    if prev is None:
        raise HTTPException(status_code=409, detail="No idea submitted yet")

    intake = run_intake(
        db, model_router, project_id=project.id, raw_text=prev.raw_text, answers=body.answers
    )
    submission = IdeaSubmission(
        project_id=project.id,
        raw_text=prev.raw_text,
        answers=body.answers,
        normalized_brief=intake.normalized_brief,
        missing_info=intake.missing_info,
    )
    db.add(submission)
    db.flush()
    record_event(
        db, event_type="intake.revised", summary="Brief revised with founder answers",
        actor_type=ActorType.agent, project_id=project.id,
        subject_type="idea_submission", subject_id=submission.id,
    )
    return IntakeOut(
        project_id=project.id, submission_id=submission.id, **intake.model_dump()
    )


@router.post(
    "/projects/{project_id}/evaluate",
    response_model=FeasibilityReportOut,
    dependencies=[Depends(rate_limit)],
)
def evaluate(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    model_router: ModelRouter = Depends(get_router),
    user: User = Depends(current_user),
) -> FeasibilityReport:
    check_daily_spend(db)
    project = owned_project(db, user, project_id)
    submission = db.scalar(
        select(IdeaSubmission)
        .where(IdeaSubmission.project_id == project_id)
        .order_by(IdeaSubmission.created_at.desc())
    )
    if submission is None or not submission.normalized_brief:
        raise HTTPException(status_code=409, detail="Run intake first")

    project.status = ProjectStatus.evaluating
    record_event(
        db, event_type="evaluation.started", summary="Feasibility evaluation started",
        actor_type=ActorType.user, project_id=project.id,
    )

    answers_summary = "\n".join(f"{q}: {a}" for q, a in (submission.answers or {}).items())
    result = run_feasibility(
        db, model_router,
        project_id=project.id,
        brief=submission.normalized_brief,
        assumptions=submission.missing_info or [],
        answers_summary=answers_summary,
    )

    version = 1 + (
        db.scalar(
            select(FeasibilityReport.version)
            .where(FeasibilityReport.project_id == project_id)
            .order_by(FeasibilityReport.version.desc())
        )
        or 0
    )
    report = FeasibilityReport(
        project_id=project.id,
        version=version,
        verdict=result.verdict,
        confidence=result.confidence,
        scores=[s.model_dump() for s in result.scores],
        mvp_scope=result.mvp_scope,
        do_not_build=result.do_not_build,
        assumptions=result.assumptions,
        validation_plan=result.validation_plan,
        reasoning=result.reasoning,
        cost_estimate=estimate_costs(len(result.mvp_scope)),
    )
    db.add(report)
    project.status = ProjectStatus.awaiting_approval
    db.flush()
    record_event(
        db, event_type="evaluation.completed",
        summary=f"Verdict: {result.verdict} (confidence {result.confidence}%)",
        actor_type=ActorType.agent, project_id=project.id,
        subject_type="feasibility_report", subject_id=report.id,
        payload={"verdict": result.verdict, "weighted_total": result.weighted_total()},
    )
    return report


@router.post("/projects/{project_id}/report/share")
def share_report(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Mint (or return the existing) public share token for the latest report."""
    import secrets

    owned_project(db, user, project_id)
    report = db.scalar(
        select(FeasibilityReport)
        .where(FeasibilityReport.project_id == project_id)
        .order_by(FeasibilityReport.version.desc())
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No feasibility report yet")
    if not report.share_token:
        report.share_token = secrets.token_urlsafe(24)
        db.flush()
        record_event(
            db, event_type="report.shared",
            summary="Public share link created for the feasibility report",
            actor_type=ActorType.user, actor_id=user.id, project_id=project_id,
            subject_type="feasibility_report", subject_id=report.id,
        )
    return {"token": report.share_token, "path": f"/share/{report.share_token}"}


@router.delete("/projects/{project_id}/report/share")
def revoke_share(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Revoke the public share link: clears the token so /share/{old} 404s."""
    owned_project(db, user, project_id)
    report = db.scalar(
        select(FeasibilityReport)
        .where(FeasibilityReport.project_id == project_id)
        .order_by(FeasibilityReport.version.desc())
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No feasibility report yet")
    if report.share_token:
        report.share_token = None
        db.flush()
        record_event(
            db, event_type="report.share_revoked",
            summary="Public share link revoked",
            actor_type=ActorType.user, actor_id=user.id, project_id=project_id,
            subject_type="feasibility_report", subject_id=report.id,
        )
    return {"revoked": True}


@router.get("/projects/{project_id}/report", response_model=FeasibilityReportOut)
def get_report(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> FeasibilityReport:
    owned_project(db, user, project_id)
    report = db.scalar(
        select(FeasibilityReport)
        .where(FeasibilityReport.project_id == project_id)
        .order_by(FeasibilityReport.version.desc())
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No feasibility report yet")
    return report
