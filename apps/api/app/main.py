import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import (
    agents, approvals, costs, health, hierarchy, ideas, projects, public, templates, work,
)
from app.services.auth import require_auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
        logger.info("sentry enabled")
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed - "
            "pip install '.[observability]'"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Durability: a killed process must not brick projects. Fail tasks the
    # previous process orphaned so runs can be recreated (see sweep docstring).
    from app.db.session import SessionLocal
    from app.services.orchestrator import sweep_stale_runs

    try:
        with SessionLocal() as db:
            swept = sweep_stale_runs(db)
            db.commit()
            if swept:
                logger.info("startup sweep: failed %d orphaned task(s)", swept)
    except Exception:
        # Boot anyway; /health/ready reports DB trouble to the platform.
        logger.exception("startup sweep failed")
    yield


app = FastAPI(
    title="Verdict API",
    description="Founder-governed, transparent AI software studio. No black boxes.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared-secret auth on every route except the health probes. Stopgap until
# per-user auth (Clerk) lands; disabled when API_AUTH_TOKEN is unset (local/
# demo dev). See app/services/auth.py.
protected = [Depends(require_auth)]

app.include_router(health.router)
app.include_router(public.router)  # deliberately unauthenticated (see module docstring)
app.include_router(projects.router, dependencies=protected)
app.include_router(ideas.router, dependencies=protected)
app.include_router(agents.router, dependencies=protected)
app.include_router(work.router, dependencies=protected)
app.include_router(approvals.router, dependencies=protected)
app.include_router(costs.router, dependencies=protected)
app.include_router(templates.router, dependencies=protected)
app.include_router(hierarchy.router, dependencies=protected)
