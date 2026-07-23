from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Pool sized for small managed Postgres tiers; recycle beats idle-connection
# reaping by the host. sqlite (tests/dev) ignores pooling knobs entirely.
_pool_kwargs = (
    {}
    if settings.database_url.startswith("sqlite")
    else {"pool_size": 3, "max_overflow": 5, "pool_recycle": 300}
)
engine = create_engine(settings.database_url, pool_pre_ping=True, **_pool_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session_factory():
    """Injectable session factory for background work (overridable in tests)."""
    return SessionLocal
