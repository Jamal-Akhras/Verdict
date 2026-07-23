"""Per-user auth: Clerk JWT verification and tenant isolation (the IDOR fix).

Two users, real RS256 JWTs against a monkeypatched JWKS. User B must get 404
(not 403 - ids leak nothing) for everything belonging to user A.
"""
import json as _json
import time
import uuid

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Base
from app.providers.router import ModelRouter, get_router
from app.services import auth as auth_service
from tests.conftest import FakeProvider
from tests.test_agents import INTAKE_JSON

ISSUER = "https://test.clerk.accounts.dev"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_pem = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
_jwk = _json.loads(pyjwt.algorithms.RSAAlgorithm.to_jwk(_key.public_key()))
_jwk["kid"] = "test-key"
JWKS = {"keys": [_jwk]}


def token_for(sub: str, email: str | None = None, expired: bool = False) -> str:
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": ISSUER,
        "iat": now - 10,
        "exp": now - 5 if expired else now + 300,
    }
    if email:
        claims["email"] = email
    return pyjwt.encode(claims, _pem, algorithm="RS256", headers={"kid": "test-key"})


def auth(sub: str) -> dict:
    return {"Authorization": f"Bearer {token_for(sub)}"}


@pytest.fixture()
def client(monkeypatch):
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

    monkeypatch.setattr(settings, "clerk_issuer", ISSUER)
    monkeypatch.setattr(auth_service, "_fetch_jwks", lambda: JWKS)
    auth_service._jwks_cache["keys"] = None  # force refetch through the fake

    scripted = ModelRouter(providers={
        "openai": FakeProvider("openai", [INTAKE_JSON] * 10),
        "anthropic": FakeProvider("anthropic", []),
    })
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_router] = lambda: scripted
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_project(client, sub: str) -> str:
    r = client.post(
        "/ideas",
        json={"name": "P", "raw_text": "a gym booking idea"},
        headers=auth(sub),
    )
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def test_requests_without_token_rejected(client):
    assert client.get("/projects").status_code == 401
    assert client.get("/projects", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_expired_token_rejected(client):
    headers = {"Authorization": f"Bearer {token_for('user_a', expired=True)}"}
    assert client.get("/projects", headers=headers).status_code == 401


def test_user_provisioned_on_first_sight(client):
    r = client.get("/projects", headers=auth("user_new"))
    assert r.status_code == 200 and r.json() == []


def test_tenants_see_only_their_projects(client):
    pid_a = make_project(client, "user_a")
    make_project(client, "user_b")
    mine = client.get("/projects", headers=auth("user_a")).json()
    assert [p["id"] for p in mine] == [pid_a]


def test_cross_tenant_access_is_404_everywhere(client):
    pid_a = make_project(client, "user_a")
    b = auth("user_b")
    assert client.get(f"/projects/{pid_a}", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/report", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/tasks", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/artifacts", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/audit", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/approvals", headers=b).status_code == 404
    assert client.get(f"/projects/{pid_a}/costs/summary", headers=b).status_code == 404
    assert client.post(f"/projects/{pid_a}/archive", headers=b).status_code == 404
    assert client.post(
        f"/projects/{pid_a}/stage", json={"stage": "prototype"}, headers=b
    ).status_code == 404
    assert client.post(f"/projects/{pid_a}/run", headers=b).status_code == 404
    # owner still gets through
    assert client.get(f"/projects/{pid_a}", headers=auth("user_a")).status_code == 200


def test_cross_tenant_agent_and_approval_access_blocked(client):
    pid_a = make_project(client, "user_a")
    a = auth("user_a")
    b = auth("user_b")
    r = client.post(f"/projects/{pid_a}/stage", json={"stage": "prototype"}, headers=a)
    agent_id = r.json()[0]["id"]
    assert client.post(f"/agents/{agent_id}/approve", headers=b).status_code == 404
    assert client.post(f"/agents/{agent_id}/approve", headers=a).status_code == 200
    fake = uuid.uuid4()
    assert client.post(f"/approvals/{fake}/approve", json={"note": ""}, headers=b).status_code == 404
