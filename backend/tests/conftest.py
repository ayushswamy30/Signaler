"""Shared test fixtures.

Model tests run against a temporary SQLite file whose schema is built by the
real Alembic migrations, so the tests exercise the same pipeline that creates a
real database. A test that built its schema with ``Base.metadata.create_all``
would pass even if the migrations were broken or missing.
"""

from collections.abc import Callable, Generator
from typing import Any
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.database.database import create_app_engine, get_db
from app.main import app
from app.models.user import User
from app.services import auth_service, user_service
from app.websocket.manager import manager

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config(database_url: str) -> Config:
    """Alembic config pointed at a specific database.

    Paths are resolved from this file rather than the working directory so the
    suite runs from anywhere.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # alembic/env.py reads this and falls back to application settings when it
    # is unset, which is what the normal CLI path does.
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """URL of a temporary SQLite file, unique per test.

    A file rather than ``:memory:`` because each in-memory connection gets its
    own empty database: the migrations would run in one connection and the test
    session would open another and find no tables.
    """
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    """Alembic config for the temporary database, for tests driving migrations."""
    return _alembic_config(database_url)


@pytest.fixture
def migrated_engine(database_url: str) -> Generator[Engine, None, None]:
    """Engine for a temporary database with all migrations applied."""
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_app_engine(database_url)
    try:
        yield engine
    finally:
        # pytest removes tmp_path itself; disposing releases the file handles
        # first, which matters on platforms that lock open files.
        engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Generator[Session, None, None]:
    """A session bound to the temporary migrated database."""
    factory = sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient whose get_db dependency yields the test session.

    Routes added in later stages get the temporary database instead of the
    developer's own, without changing how they declare the dependency.
    """

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hash with bcrypt's minimum work factor for the duration of the suite.

    The production factor is deliberately slow; at four rounds a test that
    registers a handful of accounts takes milliseconds instead of seconds.
    Autouse because every fixture below creates users.
    """
    monkeypatch.setattr(settings, "bcrypt_rounds", 4)


DEFAULT_PASSWORD = "correct-horse-battery"


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    """Factory for registered accounts.

    A factory rather than fixed fixtures: most tests need two or three users
    whose relationships differ, and naming each combination would multiply
    fixtures faster than tests.
    """

    def _make(username: str, *, display_name: str | None = None, password: str = DEFAULT_PASSWORD,
              phone_number: str | None = None) -> User:
        return user_service.create_user(
            db_session,
            username=username,
            password=password,
            display_name=display_name or username.title(),
            phone_number=phone_number,
        )

    return _make


@pytest.fixture
def alice(make_user: Callable[..., User]) -> User:
    return make_user("alice", display_name="Alice Anand")


@pytest.fixture
def bob(make_user: Callable[..., User]) -> User:
    return make_user("bob", display_name="Bob Basu")


@pytest.fixture
def carol(make_user: Callable[..., User]) -> User:
    return make_user("carol", display_name="Carol Chen")


@pytest.fixture
def authed(client: TestClient, db_session: Session) -> Callable[[User], TestClient]:
    """Return a helper that signs a client in as a given user.

    It mutates the shared client's default headers rather than building a new
    one, because both must keep using the same database session -- two clients
    would mean two identity maps over one connection.
    """

    def _as(user: User) -> TestClient:
        session = auth_service.issue_session(db_session, user)
        client.headers["Authorization"] = f"Bearer {session.access_token}"
        return client

    return _as


# --- websocket fixtures -----------------------------------------------------
#
# Shared by every test needing a live socket. They live here rather than in one
# test module because both the realtime tests and the call-signalling tests
# need the same setup, and a second copy would drift.


@pytest.fixture
def live(migrated_engine: Engine, db_session: Session) -> Generator[TestClient, None, None]:
    """A client with the application lifespan running.

    Entering the TestClient as a context manager is what makes socket tests
    meaningful: it runs the lifespan (so ``events`` has an event loop to publish
    onto) and keeps every request and socket on that one loop. Without it an
    HTTP request would run on a different loop from the socket, and no
    broadcast would ever arrive.

    Unlike the HTTP-only ``client`` fixture, this hands out a *fresh* session
    per request and per socket rather than sharing the test's. A socket holds
    its session for the whole connection, on a different thread from the test
    body, and one SQLAlchemy Session is not safe to use from two threads at
    once. Both talk to the same file, so anything the test commits is visible.
    """
    factory = sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        # The registry is process-wide, so a socket left over from a failed
        # test would otherwise receive the next test's events.
        manager._connections.clear()


@pytest.fixture
def token_for(db_session: Session) -> Callable[[User], str]:
    """Mint an access token, for the socket query string."""

    def _token(user: User) -> str:
        return auth_service.issue_session(db_session, user).access_token

    return _token


@pytest.fixture
def sign_in(live: TestClient, token_for: Callable[[User], str]) -> Callable[[User], TestClient]:
    """Sign the live client in, for HTTP calls made alongside a socket."""

    def _as(user: User) -> TestClient:
        live.headers["Authorization"] = f"Bearer {token_for(user)}"
        return live

    return _as


def drain_ready(socket: Any) -> dict:
    """Consume and return the ``ready`` frame every connection opens with."""
    frame = socket.receive_json()
    assert frame["type"] == "ready"
    return frame


def await_event(socket: Any, wanted: str, *, limit: int = 6) -> dict:
    """Read frames until one of type ``wanted`` arrives.

    A socket carries every event its user is entitled to, so a test waiting for
    one thing routinely meets another first -- a second client connecting emits
    presence, and connecting at all emits delivery receipts. Skipping keeps
    these tests about the event under test rather than about ordering.
    """
    for _ in range(limit):
        frame = socket.receive_json()
        if frame["type"] == wanted:
            return frame
    raise AssertionError(f"No {wanted!r} frame within {limit} frames.")
