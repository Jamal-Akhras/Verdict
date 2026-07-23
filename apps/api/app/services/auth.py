"""Authentication and per-user authorization.

Three modes, strongest wins:

1. Clerk per-user auth (CLERK_ISSUER set): every route requires a Clerk
   session JWT (RS256, verified against the instance JWKS); users are
   provisioned on first sight of a new `sub`; all data is tenant-scoped
   through `owned_project`/`owned` helpers.
2. Shared-secret token (API_AUTH_TOKEN set, no Clerk): one bearer token
   gates the API; everything belongs to the demo user. Single-operator
   deployments only.
3. Open dev/demo mode (neither set): no auth, demo user owns everything.

The IDOR guarantee lives in the helpers at the bottom: routes never load a
project (or anything reachable from one) by raw id - they go through
`owned_project`, which 404s on other tenants' data.
"""
import threading
import time
import uuid

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.core import Project, User
from app.services.users import get_or_create_demo_user

_JWKS_TTL_SECONDS = 900
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_jwks_lock = threading.Lock()


def _fetch_jwks() -> dict:
    resp = httpx.get(
        f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json", timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def _get_jwks() -> dict:
    with _jwks_lock:
        fresh = time.monotonic() - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS
        if _jwks_cache["keys"] is not None and fresh:
            return _jwks_cache["keys"]
    keys = _fetch_jwks()
    with _jwks_lock:
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = time.monotonic()
    return keys


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, candidate = header.partition(" ")
    if scheme.lower() != "bearer" or not candidate.strip():
        raise _unauthorized("Missing bearer token")
    return candidate.strip()


def _verify_clerk_jwt(token: str) -> dict:
    import jwt as pyjwt

    try:
        header = pyjwt.get_unverified_header(token)
    except pyjwt.PyJWTError as exc:
        raise _unauthorized("Malformed token") from exc
    jwks = _get_jwks()
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None:
        # key rotation: refresh once before giving up
        with _jwks_lock:
            _jwks_cache["keys"] = None
        jwks = _get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None:
        raise _unauthorized("Unknown signing key")
    try:
        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key)
        return pyjwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer.rstrip("/"),
            options={"verify_aud": False},  # Clerk uses azp, not aud
        )
    except pyjwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc


def _get_or_create_clerk_user(db: Session, claims: dict) -> User:
    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("Token has no subject")
    user = db.scalar(select(User).where(User.clerk_id == sub))
    if user is None:
        email = claims.get("email") or f"{sub}@users.clerk.local"
        name = claims.get("name") or claims.get("first_name")
        user = User(clerk_id=sub, email=email, name=name)
        db.add(user)
        db.flush()
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated user for this request (see module docstring
    for the three modes). Attach with `user: User = Depends(current_user)`."""
    if settings.clerk_issuer:
        claims = _verify_clerk_jwt(_bearer(request))
        return _get_or_create_clerk_user(db, claims)
    if settings.api_auth_token:
        import secrets

        if not secrets.compare_digest(_bearer_or_empty(request), settings.api_auth_token):
            raise _unauthorized("Missing or invalid API token")
        return get_or_create_demo_user(db)
    return get_or_create_demo_user(db)


def _bearer_or_empty(request: Request) -> str:
    try:
        return _bearer(request)
    except HTTPException:
        return ""


def require_auth(request: Request, db: Session = Depends(get_db)) -> None:
    """Router-level gate (kept for main.py's include_router dependencies).
    Performs the same resolution as current_user and discards the result."""
    current_user(request, db)


# --- tenant-scoping helpers (the IDOR guarantee) -----------------------------

def owned_project(db: Session, user: User, project_id: uuid.UUID) -> Project:
    """Load a project ONLY if it belongs to the user. 404 otherwise - the
    same status as 'does not exist', so ids leak nothing."""
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def owned(db: Session, user: User, obj, label: str = "Resource"):
    """Assert an object that carries project_id belongs to the user."""
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    owned_project(db, user, obj.project_id)
    return obj
