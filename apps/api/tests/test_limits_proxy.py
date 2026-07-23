"""Rate limiter must read the real client IP behind a trusted proxy and must
NOT trust a client-spoofed X-Forwarded-For when no proxy is configured."""
from types import SimpleNamespace

from app.config import settings
from app.services.limits import client_ip


def _req(xff: str | None, peer: str = "10.0.0.1"):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_no_proxy_ignores_xff(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    # attacker prepends a fake IP - must be ignored, socket peer wins
    assert client_ip(_req("1.2.3.4", peer="10.0.0.1")) == "10.0.0.1"


def test_one_proxy_reads_client_hop(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    # one trusted proxy appends the real client on the left; -1 hop is the client
    assert client_ip(_req("203.0.113.9", peer="10.0.0.1")) == "203.0.113.9"


def test_spoof_beyond_trusted_hops_is_defeated(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    # attacker sends XFF="evil, realclient"; with 1 trusted proxy we take the
    # rightmost-1 = realclient, not the attacker's prepended value
    assert client_ip(_req("9.9.9.9, 203.0.113.9", peer="10.0.0.1")) == "203.0.113.9"


def test_missing_xff_falls_back_to_peer(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert client_ip(_req(None, peer="10.0.0.1")) == "10.0.0.1"
