"""Hierarchy configuration: validation and presets.

Policy enforced here, at configuration time, so the router can trust a
pinned model at run time:
- supervisor links stay inside the project, never self, never a cycle;
- high-risk work done by a non-frontier model must be supervised by a
  frontier ("high" tier) model - cheap labour is fine, unchecked cheap
  labour on high-risk work is not.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.build_agents import DEFS_BY_SLUG
from app.models.agents import Agent, AgentStatus, Authority
from app.models.core import ActorType, Project
from app.models.hierarchy import ModelProfile, ModelTier
from app.services.agent_lifecycle import transition
from app.services.audit import record_event

INACTIVE = {AgentStatus.rejected, AgentStatus.archived}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class HierarchyError(ValueError):
    pass


def _tier(db: Session, agent: Agent) -> ModelTier:
    """Unpinned agents route through routing.yaml, whose supervision and
    high-risk entries are all high tier."""
    if agent.model_profile_id is None:
        return ModelTier.high
    profile = db.get(ModelProfile, agent.model_profile_id)
    return profile.tier if profile else ModelTier.high


def work_risk(agent: Agent) -> str:
    task_def = DEFS_BY_SLUG.get(agent.slug)
    risks = [agent.risk_level, task_def.risk_level if task_def else "low"]
    return max(risks, key=lambda r: RISK_ORDER.get(r, 0))


def validate_hierarchy(db: Session, project_id: uuid.UUID) -> list[str]:
    agents = {
        a.id: a for a in db.scalars(select(Agent).where(Agent.project_id == project_id))
    }
    errors: list[str] = []
    for agent in agents.values():
        if agent.supervisor_id is None:
            continue
        boss = agents.get(agent.supervisor_id)
        if boss is None:
            errors.append(f"{agent.name}: supervisor is not on this project")
            continue
        if boss.id == agent.id:
            errors.append(f"{agent.name} cannot supervise itself")
            continue
        seen = {agent.id}
        current = boss
        while current is not None:
            if current.id in seen:
                errors.append(f"{agent.name}: supervisor chain loops back on itself")
                break
            seen.add(current.id)
            current = agents.get(current.supervisor_id) if current.supervisor_id else None

    for agent in agents.values():
        if agent.status in INACTIVE or agent.slug not in DEFS_BY_SLUG:
            continue
        if work_risk(agent) != "high" or _tier(db, agent) == ModelTier.high:
            continue
        boss = agents.get(agent.supervisor_id) if agent.supervisor_id else None
        if boss is None or boss.status in INACTIVE:
            errors.append(
                f"{agent.name} does high-risk work on a non-frontier model, so it "
                "needs a supervisor (or a high-tier model)"
            )
        elif _tier(db, boss) != ModelTier.high:
            errors.append(
                f"{agent.name} does high-risk work on a non-frontier model, so its "
                f"supervisor ({boss.name}) must use a high-tier model"
            )
    return errors


def ensure_valid(db: Session, project_id: uuid.UUID) -> None:
    db.flush()
    errors = validate_hierarchy(db, project_id)
    if errors:
        raise HierarchyError("; ".join(errors))


@dataclass
class PresetSpec:
    shape: str  # "flat" (one director) | "teams" (director + one lead per team)
    worker_profile: ModelProfile | None
    lead_profile: ModelProfile | None
    director_profile: ModelProfile | None


def _supervisor_agent(
    db: Session, project: Project, *, slug: str, name: str, initials: str, team: str,
    role: str, profile: ModelProfile | None, budget: float,
) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.project_id == project.id, Agent.slug == slug)
    )
    if agent is None:
        agent = Agent(
            project_id=project.id, slug=slug, name=name, initials=initials, team=team,
            role=role, status=AgentStatus.proposed, authority=Authority.suggest,
            risk_level="medium", budget_max_usd=budget, created_by="user",
        )
        db.add(agent)
        db.flush()
        record_event(
            db, event_type="agent.proposed",
            summary=f"{name} added by hierarchy preset (budget ${budget:.2f})",
            actor_type=ActorType.user, project_id=project.id,
            subject_type="agent", subject_id=agent.id, payload={"slug": slug},
        )
    if agent.status == AgentStatus.proposed:
        # The founder chose the preset: that is the approval.
        transition(db, agent, AgentStatus.approved, reason="hierarchy preset")
    agent.model_profile_id = profile.id if profile else None
    return agent


def apply_preset(db: Session, project: Project, spec: PresetSpec) -> list[Agent]:
    workers = [
        a for a in db.scalars(select(Agent).where(Agent.project_id == project.id))
        if a.slug in DEFS_BY_SLUG and a.status not in INACTIVE
    ]
    if not workers:
        raise HierarchyError("No worker agents yet - choose a stage to staff the team first")

    director = _supervisor_agent(
        db, project, slug="director", name="Director", initials="DR", team="Governance",
        role="Owns the team's output quality. Reviews leads' escalations and decides "
             "everything below founder level; raises only founder-level decisions.",
        profile=spec.director_profile, budget=3.0,
    )
    director.supervisor_id = None
    leads: dict[str, Agent] = {}
    if spec.shape == "teams":
        for team in sorted({w.team for w in workers}):
            lead = _supervisor_agent(
                db, project, slug=f"lead-{team.lower()}", name=f"{team} Lead",
                initials=f"{team[:1].upper()}L", team=team,
                role=f"Reviews every {team} deliverable before the rest of the team "
                     "relies on it: sends weak drafts back with specific fixes and "
                     "escalates only what needs the Director.",
                profile=spec.lead_profile, budget=2.0,
            )
            lead.supervisor_id = director.id
            leads[team] = lead
    for worker in workers:
        worker.supervisor_id = (leads.get(worker.team) or director).id
        worker.model_profile_id = spec.worker_profile.id if spec.worker_profile else None
    ensure_valid(db, project.id)
    record_event(
        db, event_type="hierarchy.preset",
        summary=f"Hierarchy set: {spec.shape} preset over {len(workers)} worker(s)",
        actor_type=ActorType.user, project_id=project.id,
        payload={
            "shape": spec.shape,
            "worker_profile": spec.worker_profile.name if spec.worker_profile else None,
            "lead_profile": spec.lead_profile.name if spec.lead_profile else None,
            "director_profile": spec.director_profile.name if spec.director_profile else None,
        },
    )
    return [director, *leads.values(), *workers]
