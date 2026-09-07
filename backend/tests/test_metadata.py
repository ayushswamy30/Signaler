"""Tests for the SQLAlchemy metadata and Alembic plumbing.

These check the wiring itself -- that there is one Base, that the model package
is the registration point, and that Alembic reads the same metadata the
application uses. They deliberately create no application tables.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import DeclarativeBase

import app.models
from app.database.database import NAMING_CONVENTION, Base

# Resolved from this file rather than the working directory so the suite passes
# regardless of where pytest is invoked from.
BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # script_location is relative to alembic.ini, which Config does not resolve
    # on its own when invoked from another directory.
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def test_base_is_the_single_declarative_base() -> None:
    assert issubclass(Base, DeclarativeBase)
    # The registry every model shares must be the metadata Alembic reads.
    assert Base.registry.metadata is Base.metadata


def test_model_package_is_importable_and_shares_the_base_metadata() -> None:
    assert hasattr(app.models, "__all__")

    # Every name exported by the package must be a model on the shared metadata,
    # which is what makes it visible to Alembic autogenerate.
    for name in app.models.__all__:
        model = getattr(app.models, name)
        assert model.metadata is Base.metadata, f"{name} is not on the shared metadata"


def test_metadata_carries_the_naming_convention() -> None:
    # Constraint names must be deterministic; SQLite cannot alter unnamed ones.
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    for key in ("pk", "fk", "uq", "ix", "ck"):
        assert key in Base.metadata.naming_convention


def test_no_application_tables_are_defined_yet() -> None:
    # Application models arrive in A02. This guards against a stray table being
    # registered here by accident.
    assert Base.metadata.sorted_tables == []


def test_alembic_can_load_the_application_metadata() -> None:
    """Alembic must be able to diff Base.metadata against a real database."""
    # An empty in-memory database, not the project's SQLite file: this compares
    # the metadata without touching developer state.
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)

    # Zero models and an empty database must agree.
    assert diff == []


def test_migration_history_has_a_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    # Multiple heads mean branched history that "alembic upgrade head" cannot
    # resolve; catching it here is cheaper than at deploy time.
    assert len(script.get_heads()) == 1


def test_alembic_ini_does_not_hard_code_a_database_url() -> None:
    # The URL must come from app.core.config so the app and migrations cannot
    # drift onto different databases.
    assert not _alembic_config().get_main_option("sqlalchemy.url", default="")
