"""Shared test fixtures.

Model tests run against a temporary SQLite file whose schema is built by the
real Alembic migrations, so the tests exercise the same pipeline that creates a
real database. A test that built its schema with ``Base.metadata.create_all``
would pass even if the migrations were broken or missing.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.database import create_app_engine, get_db
from app.main import app

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
