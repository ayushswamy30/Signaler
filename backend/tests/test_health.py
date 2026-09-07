"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient

import app.database.database as database_module
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"]
    assert body["environment"]


def test_health_does_not_open_a_database_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health must stay usable when the database is unreachable.

    A health check that opens a session reports the database's health, not the
    application's, and fails the container liveness probe during any brief
    database blip. This makes a session attempt raise, so the endpoint only
    passes if it never touches the database.
    """

    def explode() -> None:
        raise AssertionError("health endpoint must not open a database session")

    monkeypatch.setattr(database_module, "SessionLocal", explode)

    assert client.get("/api/health").status_code == 200
