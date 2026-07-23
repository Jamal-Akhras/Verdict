"""Idempotent loader for seed agent templates (seeds/agent_templates/*.json)."""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agents import AgentTemplate, Authority

SEEDS_DIR = Path(__file__).resolve().parents[3].parent / "seeds" / "agent_templates"


def load_seed_templates(db: Session, seeds_dir: Path = SEEDS_DIR) -> int:
    """Insert any seed template (slug, version) not already in the DB."""
    loaded = 0
    for path in sorted(seeds_dir.glob("*.json")):
        data = json.loads(path.read_text())
        exists = db.scalar(
            select(AgentTemplate).where(
                AgentTemplate.slug == data["slug"],
                AgentTemplate.version == data.get("version", 1),
            )
        )
        if exists:
            continue
        db.add(
            AgentTemplate(
                slug=data["slug"],
                version=data.get("version", 1),
                name=data["name"],
                initials=data.get("initials", "AG"),
                team=data.get("team", "Strategy"),
                role=data["role"],
                scope=data.get("scope", ""),
                default_tools=data.get("tools", data.get("default_tools", [])),
                checks=data.get("checks", []),
                output_types=data.get("output_types", []),
                task_types=data.get("task_types", []),
                default_budget_usd=data.get("default_budget_usd", 1.0),
                risk_level=data.get("risk_level", "low"),
                authority_default=Authority(data.get("authority_default", "observe")),
                approval_requirement=data.get("approval_requirement", "none"),
            )
        )
        loaded += 1
    db.flush()
    return loaded
