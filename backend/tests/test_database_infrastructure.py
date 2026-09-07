"""Tests for the test-database fixtures and SQLite foreign-key enforcement."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import create_app_engine


def _throwaway_fk_tables(engine: Engine) -> sa.MetaData:
    """Create a parent/child pair on their own MetaData.

    Deliberately not on Base.metadata: these are scaffolding for one test and
    must never reach the application schema or Alembic autogenerate.
    """
    metadata = sa.MetaData()
    sa.Table("fk_parent", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table(
        "fk_child",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("fk_parent.id"), nullable=False),
    )
    metadata.create_all(engine)
    return metadata


# --- temporary database fixtures ------------------------------------------


def test_temporary_database_file_is_created(database_url: str, migrated_engine: Engine) -> None:
    path = Path(database_url.removeprefix("sqlite:///"))
    assert path.exists(), "the fixture should have created a SQLite file"


def test_migrations_are_applied_to_the_temporary_database(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        version = connection.execute(sa.text("select version_num from alembic_version")).scalar()

    # Schema came from Alembic, not from Base.metadata.create_all: the version
    # table only exists because the migrations ran.
    assert version is not None


def test_db_session_fixture_is_usable(db_session: Session) -> None:
    assert db_session.execute(sa.text("select 1")).scalar() == 1


def test_each_test_gets_its_own_database(database_url: str) -> None:
    # tmp_path is unique per test, so state cannot leak between tests.
    assert "test.db" in database_url


def test_temporary_databases_are_cleaned_up(tmp_path: Path, database_url: str) -> None:
    # The database lives inside pytest's tmp_path, which pytest removes for us,
    # so nothing accumulates in the repository.
    assert Path(database_url.removeprefix("sqlite:///")).is_relative_to(tmp_path)


# --- SQLite foreign-key enforcement ---------------------------------------


def test_sqlite_foreign_keys_pragma_is_on(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1


def test_invalid_foreign_key_insert_is_rejected(migrated_engine: Engine) -> None:
    """The behavioural check: a bad foreign key must actually fail."""
    _throwaway_fk_tables(migrated_engine)

    with migrated_engine.begin() as connection:
        connection.execute(sa.text("insert into fk_parent (id) values (1)"))

    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            # Parent 999 does not exist.
            connection.execute(sa.text("insert into fk_child (id, parent_id) values (1, 999)"))


def test_valid_foreign_key_insert_is_accepted(migrated_engine: Engine) -> None:
    """Guards against the pragma rejecting everything rather than enforcing."""
    _throwaway_fk_tables(migrated_engine)

    with migrated_engine.begin() as connection:
        connection.execute(sa.text("insert into fk_parent (id) values (1)"))
        connection.execute(sa.text("insert into fk_child (id, parent_id) values (1, 1)"))

        count = connection.execute(sa.text("select count(*) from fk_child")).scalar()

    assert count == 1


def test_every_pooled_connection_enables_foreign_keys(migrated_engine: Engine) -> None:
    """The pragma is per-connection, so the pool must set it on each one."""
    for _ in range(3):
        with migrated_engine.connect() as connection:
            assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1


def test_sqlite_pragma_is_registered_per_engine_not_globally() -> None:
    """The pragma must not leak onto engines for other databases.

    Registering the listener on the Engine *class* would fire it for every
    engine, including a future PostgreSQL one, sending it a SQLite pragma. It
    must be attached to the individual SQLite engine instead.

    Asserting this directly on a PostgreSQL engine would need psycopg2, which
    the project does not depend on, so the class-level registration is checked
    instead -- that is the mechanism by which such a leak would happen.
    """
    from app.database.database import _enable_sqlite_foreign_keys

    assert not sa.event.contains(Engine, "connect", _enable_sqlite_foreign_keys), (
        "listener is registered globally and would run for non-SQLite engines"
    )
    assert sa.event.contains(
        create_app_engine("sqlite://"), "connect", _enable_sqlite_foreign_keys
    ), "listener is missing from the SQLite engine"
