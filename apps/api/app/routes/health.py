from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "demo_mode": settings.effective_demo_mode}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness: 200 only when the database answers. Platforms route
    traffic on this; liveness stays on /health."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
