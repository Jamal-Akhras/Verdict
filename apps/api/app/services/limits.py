"""Abuse guards: per-IP rate limiting and a daily AI-spend ceiling.

Zero new dependencies, deliberately simple:

- ``rate_limit`` is an in-memory sliding-window per-IP limiter for mutating
  endpoints. Per-process state only - fine for today's single-process
  deployments; swap for Redis when the API runs multiple replicas.
- ``check_daily_spend`` sums today's CostEvents against
  ``settings.daily_spend_limit_usd`` so a stranger (or a bug) cannot burn
  unbounded provider money in one day.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai import CostEvent
from app.models.base import utcnow

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """Resolve the real client IP, honoring exactly settings.trusted_proxy_count
    reverse proxies. Behind a proxy the socket peer is the proxy, so we read
    the Nth-from-rightmost X-Forwarded-For entry - but ONLY as many hops as we
    trust, so a client cannot spoof it by prepending fake entries.
    """
    n = settings.trusted_proxy_count
    if n > 0:
        xff = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if len(hops) >= n:
            return hops[-n]  # rightmost n are trusted proxies; -n is the client
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """FastAPI dependency: sliding-window limit per client IP.

    Disabled via settings.rate_limit_enabled (tests set it False - a shared
    fake client IP would trip the limiter across unrelated tests).
    """
    if not settings.rate_limit_enabled:
        return
    ip = client_ip(request)
    now = time.monotonic()
    with _hits_lock:
        window = _hits[ip]
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests - wait a minute and try again",
            )
        window.append(now)


def daily_spend_usd(db: Session) -> float:
    """Total AI spend recorded since UTC midnight (all projects)."""
    start_of_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)).where(
            CostEvent.created_at >= start_of_day
        )
    ) or 0.0


def daily_spend_exceeded(db: Session) -> str | None:
    """Return a client-safe message when today's spend hit the ceiling."""
    limit = settings.daily_spend_limit_usd
    if limit <= 0:
        return None
    spent = daily_spend_usd(db)
    if spent >= limit:
        return (
            f"Daily AI spend limit reached (${spent:.2f} of ${limit:.2f}). "
            "Try again tomorrow or raise DAILY_SPEND_LIMIT_USD."
        )
    return None


def check_daily_spend(db: Session) -> None:
    """Raise HTTP 429 when today's AI spend has hit the ceiling."""
    message = daily_spend_exceeded(db)
    if message:
        raise HTTPException(status_code=429, detail=message)
