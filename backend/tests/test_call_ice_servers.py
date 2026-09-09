"""The one REST piece a call needs: /api/calls/ice-servers.

Signalling itself is covered in test_calls.py. This is about what server
list a client gets, and that a dead or unconfigured TURN provider degrades
to STUN-only rather than breaking the endpoint.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import call_service


def test_anonymous_requests_are_rejected(client: TestClient):
    response = client.get("/api/calls/ice-servers")
    assert response.status_code == 401


def test_without_turn_configured_it_returns_stun_only(authed, alice):
    response = authed(alice).get("/api/calls/ice-servers")
    assert response.status_code == 200
    assert response.json() == {"ice_servers": call_service.STUN_ONLY}


def test_with_turn_configured_it_passes_metered_response_through(
    authed, alice, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "metered_turn_domain", "example.metered.ca")
    monkeypatch.setattr(settings, "metered_turn_api_key", "test-key")

    metered_servers = [
        {"urls": "stun:stun.relay.metered.ca:80"},
        {"urls": "turn:global.relay.metered.ca:80", "username": "u", "credential": "c"},
    ]

    def fake_get(url, **kwargs):
        assert url == "https://example.metered.ca/api/v1/turn/credentials"
        assert kwargs["params"] == {"apiKey": "test-key"}
        return httpx.Response(200, json=metered_servers, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    response = authed(alice).get("/api/calls/ice-servers")
    assert response.status_code == 200
    assert response.json() == {"ice_servers": metered_servers}


@pytest.mark.parametrize(
    "break_it",
    [
        pytest.param(lambda: (_ for _ in ()).throw(httpx.ConnectError("down")), id="unreachable"),
        pytest.param(
            lambda: httpx.Response(
                401, json={"error": "bad key"}, request=httpx.Request("GET", "https://x")
            ).raise_for_status(),
            id="rejected-credentials",
        ),
    ],
)
def test_a_broken_turn_provider_degrades_to_stun_only(
    authed, alice, monkeypatch: pytest.MonkeyPatch, break_it
):
    monkeypatch.setattr(settings, "metered_turn_domain", "example.metered.ca")
    monkeypatch.setattr(settings, "metered_turn_api_key", "test-key")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: break_it())

    response = authed(alice).get("/api/calls/ice-servers")
    assert response.status_code == 200
    assert response.json() == {"ice_servers": call_service.STUN_ONLY}
