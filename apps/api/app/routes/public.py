"""Public, unauthenticated routes. Keep this router tiny and read-only:
everything here is reachable by anyone on the internet by design.

Share pages expose a SANITIZED verdict only - no user identity, no costs,
no audit trail, no artifacts beyond the report itself.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ai import FeasibilityReport
from app.models.core import Project

router = APIRouter(tags=["public"])


@router.get("/share/{token}")
def shared_verdict(
    token: str, response: Response, db: Session = Depends(get_db)
) -> dict[str, Any]:
    # Public and immutable-ish: let CDNs/crawlers cache so the OG-image and
    # page fetches don't amplify into uncached DB hits.
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=600"
    if not token or len(token) < 10:
        raise HTTPException(status_code=404, detail="Not found")
    report = db.scalar(
        select(FeasibilityReport).where(FeasibilityReport.share_token == token)
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Not found")
    project = db.get(Project, report.project_id)
    return {
        "project_name": project.name if project else "an idea",
        "verdict": report.verdict.value if hasattr(report.verdict, "value") else report.verdict,
        "confidence": report.confidence,
        "scores": report.scores,
        "reasoning": report.reasoning,
        "mvp_scope": report.mvp_scope,
        "do_not_build": report.do_not_build,
        "created_at": report.created_at.isoformat(),
    }
