"""Model router: task-type + risk + cost routing with write-ahead cost logging.

Quality rules enforced here:
- Write-ahead cost logging: every provider response is recorded as a
  CostEvent + ModelCall BEFORE the parsed result is returned to the caller.
  Failed parses and fallback attempts are logged too - no untracked spend.
- router_decision explains every choice (candidates, rejections, fallbacks).
- Schema validation: one repair attempt, then escalate to the next candidate.
"""
import inspect
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.ai import CostEvent, ModelCall
from app.models.core import Project
from app.providers.base import ModelProvider, ModelResponse, ProviderError

if TYPE_CHECKING:
    from app.models.hierarchy import ModelProfile

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)
_langfuse = None


def _emit_langfuse(resp: "ModelResponse", task_type: str, agent_slug: str | None,
                   cost_usd: float, parse_ok: bool) -> None:
    """Optional tracing: mirrors each model call to Langfuse when configured.
    Never raises - observability must not break the product; the DB CostEvent
    remains the source of truth either way."""
    from app.config import settings

    if not settings.langfuse_secret_key:
        return
    global _langfuse
    try:
        if _langfuse is None:
            from langfuse import Langfuse

            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        _langfuse.generation(
            name=f"{agent_slug or 'router'}/{task_type}",
            model=resp.model,
            usage={"input": resp.tokens_in, "output": resp.tokens_out},
            metadata={"provider": resp.provider, "cost_usd": cost_usd,
                      "parse_ok": parse_ok},
        )
    except ImportError:
        logger.warning(
            "LANGFUSE keys set but langfuse is not installed - "
            "pip install '.[observability]'"
        )
    except Exception:
        logger.debug("langfuse emit failed", exc_info=True)


ROUTING_PATH = Path(__file__).parent / "routing.yaml"


class RoutingError(Exception):
    """No candidate could produce a valid result (or all were priced out)."""


@dataclass
class Candidate:
    """One model the router may try: a routing-table entry or a pinned profile."""

    model: str
    provider_name: str
    provider: ModelProvider | None
    price_in: float
    price_out: float
    profile: str | None = None  # pinned profile name, for the decision log

    def price(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.price_in + tokens_out * self.price_out) / 1_000_000

    def estimate(self, system_prompt: str, user_prompt: str, max_tokens: int) -> float:
        return self.price((len(system_prompt) + len(user_prompt)) // 4, max_tokens)


ProviderFactory = Callable[["ModelProfile"], ModelProvider]


class ModelRouter:
    def __init__(
        self,
        providers: dict[str, ModelProvider],
        routing_path: Path = ROUTING_PATH,
        provider_factory: ProviderFactory | None = None,
    ):
        self.providers = providers
        table = yaml.safe_load(routing_path.read_text())
        self.models: dict[str, dict] = table["models"]
        self.task_types: dict[str, list[str]] = table["task_types"]
        self.risk_rules: dict[str, str] = table.get("risk_rules", {})
        # Builds providers for pinned model profiles (local, subscription,
        # or API models the user configured). Injectable for tests.
        self.provider_factory = provider_factory

    def _table_candidate(self, model: str) -> Candidate:
        m = self.models[model]
        return Candidate(
            model=model, provider_name=m["provider"],
            provider=self.providers.get(m["provider"]),
            price_in=m["price_in"], price_out=m["price_out"],
        )

    def _pinned_candidate(self, profile: "ModelProfile") -> Candidate:
        if self.provider_factory is None:
            from app.providers.profiles import build_provider

            provider = build_provider(profile)
        else:
            provider = self.provider_factory(profile)
        return Candidate(
            model=profile.model, provider_name=profile.provider.value, provider=provider,
            price_in=profile.price_in, price_out=profile.price_out, profile=profile.name,
        )

    def _candidates(self, task_type: str, risk_level: str) -> tuple[list[str], list[dict]]:
        names = self.task_types.get(task_type)
        if not names:
            raise RoutingError(f"No routing entry for task_type '{task_type}'")
        rejected: list[dict] = []
        required_tier = self.risk_rules.get("high_requires_tier")
        if risk_level == "high" and required_tier:
            kept = [n for n in names if self.models[n]["tier"] == required_tier]
            rejected = [
                {"model": n, "reason": f"risk=high requires tier={required_tier}"}
                for n in names
                if n not in kept
            ]
            names = kept
        if not names:
            raise RoutingError(f"No candidates for '{task_type}' at risk={risk_level}")
        return names, rejected

    def _log(
        self,
        db: Session,
        *,
        resp: ModelResponse,
        candidate: Candidate,
        task_type: str,
        project_id: uuid.UUID | None,
        agent_slug: str | None,
        system_prompt: str,
        user_prompt: str,
        schema_name: str | None,
        parse_ok: bool,
        decision: dict[str, Any],
        task_id: uuid.UUID | None = None,
        call_role: str = "work",
    ) -> CostEvent:
        cost = candidate.price(resp.tokens_in, resp.tokens_out)
        event = CostEvent(
            project_id=project_id,
            agent_slug=agent_slug,
            task_type=task_type,
            provider=resp.provider,
            model=resp.model,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            cost_usd=cost,
            latency_ms=resp.latency_ms,
            task_id=task_id,
            call_role=call_role,
        )
        db.add(event)
        db.flush()
        db.add(
            ModelCall(
                cost_event_id=event.id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text=resp.text,
                output_schema_name=schema_name,
                parse_ok=parse_ok,
                router_decision=decision,
            )
        )
        if project_id is not None:
            # Atomic increment: concurrent runs must not lose spend to a
            # read-modify-write race on the ORM attribute.
            db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(budget_used_usd=Project.budget_used_usd + cost)
            )
        db.flush()
        _emit_langfuse(resp, task_type, agent_slug, cost, parse_ok)
        return event

    def run(
        self,
        db: Session,
        *,
        task_type: str,
        output_schema: type[T],
        system_prompt: str,
        user_prompt: str,
        risk_level: str = "low",
        max_cost_usd: float = 1.0,
        max_tokens: int = 4000,
        project_id: uuid.UUID | None = None,
        agent_slug: str | None = None,
        pinned: "ModelProfile | None" = None,
        task_id: uuid.UUID | None = None,
        call_role: str = "work",
    ) -> T:
        """Route and execute one structured call.

        `pinned` bypasses the routing table: the founder chose this model for
        the agent, so there is no silent fallback to a paid model if, say, a
        local server is down - the call fails and the task shows why. Risk
        policy for pinned models is enforced when the hierarchy is configured
        (services/hierarchy.py), not here.
        """
        if pinned is not None:
            candidates = [self._pinned_candidate(pinned)]
            rejected: list[dict] = []
        else:
            names, rejected = self._candidates(task_type, risk_level)
            candidates = [self._table_candidate(n) for n in names]
        attempts: list[dict] = []
        cost_skips = 0
        schema = output_schema.model_json_schema()

        for cand in candidates:
            model_name = cand.model
            provider = cand.provider
            if provider is None:
                attempts.append({"model": model_name, "outcome": f"provider '{cand.provider_name}' not registered"})
                continue
            est = cand.estimate(system_prompt, user_prompt, max_tokens)
            if est > max_cost_usd:
                attempts.append({"model": model_name, "outcome": f"skipped: est ${est:.3f} > ceiling"})
                cost_skips += 1
                continue

            prompt = user_prompt
            for attempt in ("first", "repair"):
                decision = {
                    "task_type": task_type,
                    "risk_level": risk_level,
                    "chosen": model_name,
                    "attempt": attempt,
                    "rejected_by_risk": rejected,
                    "prior_attempts": list(attempts),
                    "estimated_cost_usd": round(est, 4),
                    "call_role": call_role,
                }
                if cand.profile is not None:
                    decision["pinned_profile"] = cand.profile
                extra: dict[str, Any] = {}
                if _accepts_json_schema(provider):
                    # Native structured outputs where supported; providers
                    # without the kwarg keep the json_output+_extract_json path.
                    extra["json_schema"] = schema
                try:
                    resp = provider.complete(
                        model=model_name,
                        system_prompt=system_prompt,
                        user_prompt=prompt,
                        json_output=True,
                        max_tokens=max_tokens,
                        **extra,
                    )
                except ProviderError as exc:
                    attempts.append({"model": model_name, "outcome": f"provider error: {exc}"})
                    break  # next candidate

                try:
                    parsed = output_schema.model_validate(_extract_json(resp.text))
                    self._log(
                        db, resp=resp, candidate=cand, task_type=task_type,
                        project_id=project_id, agent_slug=agent_slug,
                        system_prompt=system_prompt, user_prompt=prompt,
                        schema_name=output_schema.__name__, parse_ok=True, decision=decision,
                        task_id=task_id, call_role=call_role,
                    )
                    return parsed
                except (ValidationError, ValueError) as exc:
                    self._log(
                        db, resp=resp, candidate=cand, task_type=task_type,
                        project_id=project_id, agent_slug=agent_slug,
                        system_prompt=system_prompt, user_prompt=prompt,
                        schema_name=output_schema.__name__, parse_ok=False, decision=decision,
                        task_id=task_id, call_role=call_role,
                    )
                    attempts.append({"model": model_name, "outcome": f"parse failed ({attempt})"})
                    if attempt == "first":
                        # Real repair: show the model what it produced and why
                        # it failed, so the fix is targeted, not a blind retry.
                        prompt = (
                            f"{user_prompt}\n\n"
                            f"Your previous response failed validation.\n"
                            f"Validation error:\n{str(exc)[:2000]}\n\n"
                            f"Your previous (invalid) response was:\n"
                            f"{resp.text[:2000]}\n\n"
                            f"Fix the problems above and return ONLY a valid JSON "
                            f"object matching the required schema."
                        )
                    # after repair failure: fall through to next candidate

        if cost_skips == len(candidates):
            raise RoutingError(
                f"Cost ceiling: every candidate for '{task_type}' was estimated above "
                f"max_cost_usd=${max_cost_usd:.2f}: {attempts}"
            )
        raise RoutingError(f"All candidates failed for '{task_type}': {attempts}")


def _accepts_json_schema(provider: ModelProvider) -> bool:
    """True if the provider's complete() accepts the json_schema kwarg.

    Lets native-structured-output providers coexist with providers that
    predate the kwarg (which keep working via json_output + _extract_json).
    """
    try:
        params = inspect.signature(provider.complete).parameters
    except (TypeError, ValueError):  # builtins/mocks without signatures
        return False
    return "json_schema" in params or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in response")
    return json.loads(text[start : end + 1])


_default_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _default_router
    if _default_router is None:
        from app.config import settings

        if settings.effective_demo_mode:
            from app.providers.demo_provider import DemoProvider

            demo = DemoProvider()
            # every routed provider resolves to the demo engine
            _default_router = ModelRouter(
                providers={"openai": demo, "anthropic": demo, "gemini": demo}
            )
        else:
            from app.providers.anthropic_provider import AnthropicProvider
            from app.providers.gemini_provider import GeminiProvider
            from app.providers.openai_provider import OpenAIProvider

            _default_router = ModelRouter(
                providers={
                    "openai": OpenAIProvider(),
                    "anthropic": AnthropicProvider(),
                    "gemini": GeminiProvider(),
                }
            )
    return _default_router
