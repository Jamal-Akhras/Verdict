"""Hierarchy API: model profiles, per-agent configuration, presets, flags,
and the full prompt/work trace."""
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.agents import Agent
from app.models.ai import CostEvent, ModelCall
from app.models.core import ActorType, User
from app.models.hierarchy import (
    ACCESS_BY_PROVIDER,
    Flag,
    ModelProfile,
    ModelTier,
    ProviderKind,
    ReviewRecord,
)
from app.routes.agents import _with_costs
from app.schemas.agent import AgentOut
from app.schemas.project import ProjectOut
from app.services.audit import record_event
from app.services.auth import current_user, owned, owned_project
from app.services.hierarchy import HierarchyError, PresetSpec, apply_preset, ensure_valid

router = APIRouter(tags=["hierarchy"])


# --- model profiles -----------------------------------------------------------

def _check_http_url(v: str) -> str:
    v = v.strip()
    if v:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL")
    return v


class ModelProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: ProviderKind
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(default="", max_length=500)
    tier: ModelTier | None = None
    price_in: float | None = Field(default=None, ge=0, le=1000)
    price_out: float | None = Field(default=None, ge=0, le=1000)

    @field_validator("base_url")
    @classmethod
    def http_url(cls, v: str) -> str:
        return _check_http_url(v)


class ModelProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    provider: ProviderKind
    access: str
    model: str
    base_url: str
    tier: ModelTier
    price_in: float
    price_out: float
    created_at: datetime


def _owned_profile(db: Session, user: User, profile_id: uuid.UUID) -> ModelProfile:
    profile = db.get(ModelProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(status_code=404, detail="Model profile not found")
    return profile


def _apply_profile_fields(profile: ModelProfile, body: ModelProfileIn) -> None:
    access = ACCESS_BY_PROVIDER[body.provider]
    if access != "api" and not settings.local_providers_allowed:
        raise HTTPException(
            status_code=403,
            detail="Local and subscription models are disabled on this deployment "
                   "(ALLOW_LOCAL_PROVIDERS)",
        )
    if access == "subscription":
        from app.providers.cli_provider import validate_cli_model

        try:
            validate_cli_model(body.model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.provider == ProviderKind.local and not (body.base_url or settings.local_llm_base_url):
        raise HTTPException(
            status_code=422,
            detail="Local models need a base_url (or LOCAL_LLM_BASE_URL on the server)",
        )
    from app.providers.router import get_router

    known = get_router().models.get(body.model, {})
    if access == "api":
        price_in = body.price_in if body.price_in is not None else known.get("price_in")
        price_out = body.price_out if body.price_out is not None else known.get("price_out")
        if price_in is None or price_out is None:
            raise HTTPException(
                status_code=422,
                detail=f"'{body.model}' is not in the built-in catalog: give price_in and "
                       "price_out (USD per 1M tokens) so spend is tracked honestly",
            )
    else:
        # Local and subscription calls cost nothing per token.
        price_in = price_out = 0.0
    default_tier = ModelTier.local if access == "local" else ModelTier(known.get("tier", "high"))
    profile.name = body.name
    profile.provider = body.provider
    profile.model = body.model
    profile.base_url = body.base_url if body.provider == ProviderKind.local else ""
    profile.tier = body.tier or default_tier
    profile.price_in = price_in
    profile.price_out = price_out


@router.get("/models/catalog")
def model_catalog() -> dict[str, Any]:
    from app.providers.profiles import SUGGESTED_PROFILES, provider_status
    from app.providers.router import get_router

    table = get_router().models
    return {
        "demo_mode": settings.effective_demo_mode,
        "providers": provider_status(),
        "api_models": [
            {"model": name, **{k: m[k] for k in ("provider", "tier", "price_in", "price_out")}}
            for name, m in table.items()
        ],
        "suggested": SUGGESTED_PROFILES,
        "local_base_url": settings.local_llm_base_url,
    }


@router.get("/models/local")
def discover_local_models(base_url: str = "") -> dict[str, Any]:
    """List models installed on a local server, so the UI can offer them."""
    if not settings.local_providers_allowed:
        raise HTTPException(status_code=403, detail="Local models are disabled on this deployment")
    try:
        url = _check_http_url(base_url) or settings.local_llm_base_url
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=422, detail="No base_url given or configured")
    from app.providers.base import ProviderError
    from app.providers.local_provider import LocalProvider

    try:
        return {"base_url": url, "models": LocalProvider(base_url=url).list_models()}
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach {url}: {exc}") from exc


@router.get("/model-profiles", response_model=list[ModelProfileOut])
def list_profiles(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(db.scalars(
        select(ModelProfile).where(ModelProfile.user_id == user.id).order_by(ModelProfile.name)
    ))


@router.post("/model-profiles", response_model=ModelProfileOut)
def create_profile(
    body: ModelProfileIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    profile = ModelProfile(user_id=user.id)
    _apply_profile_fields(profile, body)
    db.add(profile)
    db.flush()
    return profile


@router.put("/model-profiles/{profile_id}", response_model=ModelProfileOut)
def update_profile(
    profile_id: uuid.UUID, body: ModelProfileIn,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    profile = _owned_profile(db, user, profile_id)
    _apply_profile_fields(profile, body)
    # A tier change can break the high-risk supervision rule anywhere the
    # profile is used.
    for project_id in set(db.scalars(
        select(Agent.project_id).where(Agent.model_profile_id == profile.id)
    )):
        try:
            ensure_valid(db, project_id)
        except HierarchyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.flush()
    return profile


@router.delete("/model-profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> None:
    profile = _owned_profile(db, user, profile_id)
    in_use = db.scalar(select(Agent.name).where(Agent.model_profile_id == profile.id))
    if in_use:
        raise HTTPException(status_code=409, detail=f"In use by {in_use}; reassign it first")
    db.delete(profile)


# --- per-agent and per-project configuration ----------------------------------

class AgentConfigIn(BaseModel):
    """PATCH semantics: only fields present in the body change; an explicit
    null clears (model -> routing table, supervisor -> founder)."""

    model_profile_id: uuid.UUID | None = None
    supervisor_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=8000)
    max_revisions: int | None = Field(default=None, ge=0, le=5)
    requires_approval: bool | None = None


@router.patch("/agents/{agent_id}/config", response_model=AgentOut)
def configure_agent(
    agent_id: uuid.UUID, body: AgentConfigIn,
    db: Session = Depends(get_db), user: User = Depends(current_user),
) -> AgentOut:
    agent = owned(db, user, db.get(Agent, agent_id), "Agent")
    changed = body.model_fields_set
    before = {f: getattr(agent, f) for f in changed}
    if "model_profile_id" in changed:
        if body.model_profile_id is not None:
            _owned_profile(db, user, body.model_profile_id)
        agent.model_profile_id = body.model_profile_id
    if "supervisor_id" in changed:
        if body.supervisor_id is not None:
            boss = db.get(Agent, body.supervisor_id)
            if boss is None or boss.project_id != agent.project_id:
                raise HTTPException(status_code=422, detail="Supervisor must be on the same project")
        agent.supervisor_id = body.supervisor_id
    if "instructions" in changed:
        agent.instructions = body.instructions or ""
    if "max_revisions" in changed and body.max_revisions is not None:
        agent.max_revisions = body.max_revisions
    if "requires_approval" in changed:
        agent.requires_approval = body.requires_approval
    try:
        ensure_valid(db, agent.project_id)
    except HierarchyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_event(
        db, event_type="agent.configured",
        summary=f"{agent.name} configuration changed: {', '.join(sorted(changed)) or 'nothing'}",
        actor_type=ActorType.user, project_id=agent.project_id,
        subject_type="agent", subject_id=agent.id,
        payload={f: {"from": _jsonable(before[f]), "to": _jsonable(getattr(agent, f))}
                 for f in changed},
    )
    return _with_costs(db, [agent])[0]


def _jsonable(v: Any) -> Any:
    return str(v) if isinstance(v, uuid.UUID) else v


class ProjectConfigIn(BaseModel):
    instructions: str = Field(default="", max_length=8000)


@router.patch("/projects/{project_id}/config", response_model=ProjectOut)
def configure_project(
    project_id: uuid.UUID, body: ProjectConfigIn,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    project = owned_project(db, user, project_id)
    project.instructions = body.instructions
    record_event(
        db, event_type="project.configured", summary="Project instructions updated",
        actor_type=ActorType.user, project_id=project.id,
        subject_type="project", subject_id=project.id,
        payload={"instructions": body.instructions},
    )
    return project


class PresetIn(BaseModel):
    shape: Literal["flat", "teams"] = "teams"
    worker_profile_id: uuid.UUID | None = None
    lead_profile_id: uuid.UUID | None = None
    director_profile_id: uuid.UUID | None = None


@router.post("/projects/{project_id}/hierarchy/preset", response_model=list[AgentOut])
def hierarchy_preset(
    project_id: uuid.UUID, body: PresetIn,
    db: Session = Depends(get_db), user: User = Depends(current_user),
) -> list[AgentOut]:
    project = owned_project(db, user, project_id)

    def profile(pid: uuid.UUID | None) -> ModelProfile | None:
        return _owned_profile(db, user, pid) if pid else None

    spec = PresetSpec(
        shape=body.shape,
        worker_profile=profile(body.worker_profile_id),
        lead_profile=profile(body.lead_profile_id),
        director_profile=profile(body.director_profile_id),
    )
    try:
        apply_preset(db, project, spec)
    except HierarchyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    agents = list(db.scalars(
        select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)
    ))
    return _with_costs(db, agents)


# --- flags and trace -----------------------------------------------------------

class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    artifact_id: uuid.UUID | None
    raised_by_agent_id: uuid.UUID
    holder_agent_id: uuid.UUID | None
    severity: str
    title: str
    detail: str
    status: str
    chain: list[Any]
    resolution: str
    approval_request_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    worker_agent_id: uuid.UUID
    reviewer_agent_id: uuid.UUID
    attempt: int
    decision: str
    summary: str
    feedback: str
    issues: list[Any]
    reviewed_output: dict[str, Any]
    created_at: datetime


class CallOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    agent_slug: str | None
    call_role: str
    task_type: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    created_at: datetime
    system_prompt: str
    user_prompt: str
    response_text: str
    parse_ok: bool
    router_decision: dict[str, Any]


class TraceOut(BaseModel):
    calls: list[CallOut]
    reviews: list[ReviewOut]
    flags: list[FlagOut]


@router.get("/projects/{project_id}/flags", response_model=list[FlagOut])
def list_flags(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    owned_project(db, user, project_id)
    return list(db.scalars(
        select(Flag).where(Flag.project_id == project_id).order_by(Flag.created_at.desc())
    ))


@router.get("/projects/{project_id}/trace", response_model=TraceOut)
def project_trace(
    project_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TraceOut:
    """Every model call (full prompts and responses), review, and escalation
    for the project or one task, oldest first: the no-black-box record."""
    owned_project(db, user, project_id)
    q = (
        select(CostEvent, ModelCall)
        .join(ModelCall, ModelCall.cost_event_id == CostEvent.id)
        .where(CostEvent.project_id == project_id)
    )
    rq = select(ReviewRecord).where(ReviewRecord.project_id == project_id)
    fq = select(Flag).where(Flag.project_id == project_id)
    if task_id is not None:
        q = q.where(CostEvent.task_id == task_id)
        rq = rq.where(ReviewRecord.task_id == task_id)
        fq = fq.where(Flag.task_id == task_id)
    rows = db.execute(q.order_by(CostEvent.created_at).limit(limit)).all()
    calls = [
        CallOut(
            id=ev.id, task_id=ev.task_id, agent_slug=ev.agent_slug, call_role=ev.call_role,
            task_type=ev.task_type, provider=ev.provider, model=ev.model,
            tokens_in=ev.tokens_in, tokens_out=ev.tokens_out, cost_usd=ev.cost_usd,
            latency_ms=ev.latency_ms, created_at=ev.created_at,
            system_prompt=mc.system_prompt, user_prompt=mc.user_prompt,
            response_text=mc.response_text, parse_ok=mc.parse_ok,
            router_decision=mc.router_decision,
        )
        for ev, mc in rows
    ]
    return TraceOut(
        calls=calls,
        reviews=[ReviewOut.model_validate(r)
                 for r in db.scalars(rq.order_by(ReviewRecord.created_at))],
        flags=[FlagOut.model_validate(f) for f in db.scalars(fq.order_by(Flag.created_at))],
    )
