import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.providers.base import ModelResponse, ProviderError


@pytest.fixture(autouse=True)
def _reset_security_guards(monkeypatch):
    """The auth token and rate limiter are process-global; keep tests
    hermetic. The limiter is off by default because every TestClient
    request shares one fake client IP - unrelated tests would trip it.
    Tests that exercise the guards monkeypatch them back on."""
    from app.config import settings
    from app.services import limits

    monkeypatch.setattr(settings, "api_auth_token", "")
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    limits._hits.clear()
    yield


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class FakeProvider:
    """Scriptable provider: queue of responses or exceptions."""

    def __init__(self, name: str, script: list, tokens_out: int = 200):
        self.name = name
        self.script = list(script)
        self.tokens_out = tokens_out
        self.calls: list[dict] = []

    def complete(self, *, model, system_prompt, user_prompt, json_output, max_tokens,
                 json_schema=None):
        self.calls.append({
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "json_schema": json_schema,
        })
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return ModelResponse(
            provider=self.name, model=model, text=item,
            tokens_in=100, tokens_out=self.tokens_out, latency_ms=5,
        )


def ok_json(payload: dict) -> str:
    return json.dumps(payload)


def provider_error(msg: str = "boom") -> ProviderError:
    return ProviderError(msg)
