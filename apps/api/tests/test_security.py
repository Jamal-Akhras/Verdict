"""P0 security guards: bearer auth, daily spend ceiling, rate limiting,
and Gemini key handling (header, never URL or exception text)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Base
from app.models.ai import CostEvent
from app.providers.base import ProviderError
from app.providers.gemini_provider import GeminiProvider
from app.providers.router import ModelRouter, get_router
from tests.conftest import FakeProvider
from tests.test_agents import INTAKE_JSON


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db: Session = TestingSession()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    scripted = ModelRouter(providers={
        "openai": FakeProvider("openai", [INTAKE_JSON] * 5),
        "anthropic": FakeProvider("anthropic", []),
    })
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_router] = lambda: scripted
    c = TestClient(app)
    c.session_factory = TestingSession
    yield c
    app.dependency_overrides.clear()


# --- auth ------------------------------------------------------------------

def test_auth_disabled_when_no_token_configured(client):
    # conftest guarantees api_auth_token == "" here
    assert client.get("/projects").status_code == 200


def test_auth_required_when_token_set(client, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_token", "sekrit-token")

    assert client.get("/projects").status_code == 401
    r = client.get("/projects", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    r = client.get("/projects", headers={"Authorization": "Basic sekrit-token"})
    assert r.status_code == 401
    # mutating routes are covered too
    r = client.post("/ideas", json={"name": "X", "raw_text": "a gym booking idea"})
    assert r.status_code == 401

    # health probes stay open for the platform
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 200

    # the right token gets through
    r = client.get("/projects", headers={"Authorization": "Bearer sekrit-token"})
    assert r.status_code == 200


# --- daily spend ceiling -----------------------------------------------------

def test_daily_spend_ceiling_blocks_ideas(client, monkeypatch):
    monkeypatch.setattr(settings, "daily_spend_limit_usd", 1.0)
    with client.session_factory() as db:
        db.add(CostEvent(
            task_type="intake", provider="openai", model="gpt-fake", cost_usd=1.5,
        ))
        db.commit()

    r = client.post("/ideas", json={"name": "X", "raw_text": "a gym booking idea"})
    assert r.status_code == 429
    assert "spend limit" in r.json()["detail"].lower()


def test_daily_spend_under_ceiling_allows_ideas(client, monkeypatch):
    monkeypatch.setattr(settings, "daily_spend_limit_usd", 1.0)
    with client.session_factory() as db:
        db.add(CostEvent(
            task_type="intake", provider="openai", model="gpt-fake", cost_usd=0.10,
        ))
        db.commit()

    r = client.post("/ideas", json={"name": "X", "raw_text": "a gym booking idea"})
    assert r.status_code == 200, r.text


# --- rate limiting -----------------------------------------------------------

def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    for _ in range(2):
        r = client.post("/ideas", json={"name": "Idea", "raw_text": "a gym booking idea"})
        assert r.status_code == 200, r.text
    r = client.post("/ideas", json={"name": "Idea", "raw_text": "a gym booking idea"})
    assert r.status_code == 429
    # GET routes are not rate limited
    assert client.get("/projects").status_code == 200


# --- gemini key handling -----------------------------------------------------

class _FakeGeminiResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "candidates": [{"content": {"parts": [{"text": "hello"}]}}],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
        }


def test_gemini_sends_key_in_header_not_query(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeGeminiResponse()

    monkeypatch.setattr("app.providers.gemini_provider.httpx.post", fake_post)
    provider = GeminiProvider(api_key="top-secret-key")
    resp = provider.complete(
        model="gemini-fake", system_prompt="s", user_prompt="u",
        json_output=True, max_tokens=100,
    )
    assert resp.text == "hello"
    assert captured["headers"]["x-goog-api-key"] == "top-secret-key"
    assert "params" not in captured
    assert "top-secret-key" not in captured["url"]


def test_gemini_error_carries_class_name_not_exception_text(monkeypatch):
    def fake_post(url, **kwargs):
        raise RuntimeError("request to ...?key=top-secret-key failed")

    monkeypatch.setattr("app.providers.gemini_provider.httpx.post", fake_post)
    provider = GeminiProvider(api_key="top-secret-key")
    with pytest.raises(ProviderError) as excinfo:
        provider.complete(
            model="gemini-fake", system_prompt="s", user_prompt="u",
            json_output=False, max_tokens=100,
        )
    assert "top-secret-key" not in str(excinfo.value)
    assert "RuntimeError" in str(excinfo.value)
