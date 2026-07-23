"""Real-model quality pass: golden briefs through intake -> feasibility.

Runs each brief N times against whatever the router is configured with
(.env keys; demo mode with no keys = smoke test only) and scores:

- band hit rate: does the verdict land in the expected band?
- flip rate: how often the same brief gets different verdicts across repeats
- validator failures, cost per verdict, total spend

Usage (from apps/api):
    python -m scripts.quality_pass                # all briefs, 3 repeats
    python -m scripts.quality_pass --repeats 1
    python -m scripts.quality_pass --briefs clear_kill,gym_booking

Exit code 1 when band hit rate < --threshold (default 0.7).
"""
import argparse
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.agents.feasibility import run_feasibility  # noqa: E402
from app.agents.intake import run_intake  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.ai import CostEvent  # noqa: E402
from app.models.core import Project, User  # noqa: E402
from app.providers.router import RoutingError, get_router  # noqa: E402

# Golden briefs: raw idea text + the verdict band a well-calibrated analyst
# should land in. Bands are deliberately wide - we test calibration, not
# clairvoyance.
GOLDEN_BRIEFS: dict[str, dict] = {
    "clear_kill": {
        "raw_text": (
            "A brand new social network for everyone in the world to replace "
            "Facebook and Instagram. I have no budget, no team, no specific "
            "niche, and I'll figure out how it makes money later."
        ),
        "band": {"kill", "park", "research"},
    },
    "crowded_todo": {
        "raw_text": (
            "A to-do list app with reminders and tags. Like Todoist but "
            "cleaner. For everyone who wants to be productive."
        ),
        "band": {"kill", "park", "research", "validate"},
    },
    "gym_booking": {
        "raw_text": (
            "A web app for boutique gyms (5-50 classes a week) to manage "
            "class schedules, member bookings, and payments - replacing "
            "WhatsApp threads and spreadsheets. Three gym owners I know have "
            "asked for this and pay $139/mo for tools they hate."
        ),
        "band": {"validate", "prototype", "build"},
    },
    "internal_tool": {
        "raw_text": (
            "An internal tool for my own accounting practice that converts "
            "client bank CSV exports into our ledger import format. My three "
            "staff lose two hours a day to this; only we will use it."
        ),
        "band": {"validate", "prototype", "build"},
    },
    "ambiguous_marketplace": {
        "raw_text": (
            "A marketplace connecting dog owners with local dog walkers. "
            "Walkers set prices, we take 15%. Starting in my city."
        ),
        "band": {"research", "validate", "prototype"},
    },
    "regulated_health": {
        "raw_text": (
            "An app where therapists store session notes and patient mental "
            "health histories, with AI summaries. Solo founder, no healthcare "
            "background, want to launch in two months."
        ),
        "band": {"kill", "park", "research", "validate"},
        # calibration probe: risk_compliance must NOT be scored rosily
        "max_risk_compliance_score": 7,
    },
}


def run_pass(brief_names: list[str], repeats: int, threshold: float) -> int:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    router = get_router()
    demo = settings.effective_demo_mode
    if demo:
        print("WARNING: no provider keys configured - demo mode returns canned")
        print("outputs, so this is a plumbing smoke test, NOT a quality pass.")
        print("Set GEMINI_API_KEY (free: https://aistudio.google.com) in .env.\n")

    hits = 0
    total = 0
    failures: list[str] = []
    rows: list[str] = []

    with Session(engine) as db:
        user = User(clerk_id="quality-pass", email="qa@verdict.local")
        db.add(user)
        db.flush()

        for name in brief_names:
            spec = GOLDEN_BRIEFS[name]
            verdicts: Counter = Counter()
            for i in range(repeats):
                project = Project(user_id=user.id, name=f"{name}-{i}")
                db.add(project)
                db.flush()
                try:
                    intake = run_intake(
                        db, router, project_id=project.id, raw_text=spec["raw_text"]
                    )
                    report = run_feasibility(
                        db, router,
                        project_id=project.id,
                        brief=intake.normalized_brief,
                        assumptions=intake.assumptions,
                    )
                except RoutingError as exc:
                    failures.append(f"{name}#{i}: RoutingError {str(exc)[:120]}")
                    continue
                verdicts[report.verdict] += 1
                total += 1
                if report.verdict in spec["band"]:
                    hits += 1
                else:
                    failures.append(
                        f"{name}#{i}: verdict '{report.verdict}' outside band {sorted(spec['band'])}"
                    )
                cap = spec.get("max_risk_compliance_score")
                if cap is not None:
                    rc = next(
                        (s.score for s in report.scores if s.category == "risk_compliance"),
                        None,
                    )
                    if rc is not None and rc > cap:
                        failures.append(
                            f"{name}#{i}: risk_compliance scored {rc} (> {cap}) on a "
                            "regulated-health idea - calibration problem"
                        )
            flip = len(verdicts) > 1
            rows.append(
                f"  {name:<24} verdicts={dict(verdicts)}"
                + ("  FLIPPED" if flip else "")
            )

        spend = db.scalar(select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)))

    print("Quality pass results")
    print("--------------------")
    for row in rows:
        print(row)
    rate = hits / total if total else 0.0
    print(f"\nband hit rate: {hits}/{total} ({rate:.0%})  threshold: {threshold:.0%}")
    print(f"total AI spend: ${spend:.4f}" + ("  (simulated - demo mode)" if demo else ""))
    if failures:
        print("\nfindings:")
        for f in failures:
            print(f"  - {f}")
    if total == 0:
        print("\nNO RUNS COMPLETED - check provider keys and routing.")
        return 1
    if rate < threshold and not demo:
        print("\nFAIL: verdicts are not calibrated to the golden bands.")
        print("Tune prompts/feasibility.md and re-run before charging users.")
        return 1
    print("\nPASS" + (" (smoke only - run with real keys for a true pass)" if demo else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument(
        "--briefs", type=str, default="",
        help="comma-separated subset, e.g. clear_kill,gym_booking",
    )
    args = parser.parse_args()
    names = (
        [n.strip() for n in args.briefs.split(",") if n.strip()]
        if args.briefs
        else list(GOLDEN_BRIEFS)
    )
    unknown = [n for n in names if n not in GOLDEN_BRIEFS]
    if unknown:
        parser.error(f"unknown briefs: {unknown}; available: {list(GOLDEN_BRIEFS)}")
    return run_pass(names, args.repeats, args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
