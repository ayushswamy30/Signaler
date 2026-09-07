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


def _exported_models() -> dict[str, type]:
    """The mapped classes app.models exports.

    The package also exports enums used by those models (ConversationType,
    ParticipantRole), which are not mapped and have no metadata, so they are
    filtered out here rather than excluded from __all__.
    """
    exported = {name: getattr(app.models, name) for name in app.models.__all__}
    return {
        name: obj
        for name, obj in exported.items()
        if isinstance(obj, type) and hasattr(obj, "__tablename__")
    }


def test_model_package_is_importable_and_shares_the_base_metadata() -> None:
    assert hasattr(app.models, "__all__")

    # Every exported model must sit on the shared metadata, which is what makes
    # it visible to Alembic autogenerate.
    for name, model in _exported_models().items():
        assert model.metadata is Base.metadata, f"{name} is not on the shared metadata"


def test_every_registered_table_has_an_exported_model() -> None:
    """Catches a model that reaches the metadata without being exported.

    Such a model would migrate correctly but be invisible to callers importing
    from app.models, so the two sets must match exactly.
    """
    exported_tables = {model.__tablename__ for model in _exported_models().values()}

    assert exported_tables == set(Base.metadata.tables)


def test_metadata_carries_the_naming_convention() -> None:
    # Constraint names must be deterministic; SQLite cannot alter unnamed ones.
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    for key in ("pk", "fk", "uq", "ix", "ck"):
        assert key in Base.metadata.naming_convention


def test_registered_models_are_on_the_shared_metadata() -> None:
    """Guards model registration, the way the zero-table check used to.

    Before A02 this asserted the metadata was empty. Now that real models
    exist, the same intent is served by pinning the set of registered tables:
    a model added without being imported in app/models/__init__.py, or a table
    registered by accident, both show up here.
    """
    assert set(Base.metadata.tables) == {
        "users",
        "contacts",
        "conversations",
        "conversation_participants",
        "messages",
        "message_status",
        "refresh_tokens",
    }


def test_models_are_registered() -> None:
    from app.models import (
        Contact,
        Conversation,
        ConversationParticipant,
        Message,
        MessageStatus,
        User,
    )

    for model, table_name in (
        (User, "users"),
        (Contact, "contacts"),
        (Conversation, "conversations"),
        (ConversationParticipant, "conversation_participants"),
        (Message, "messages"),
        (MessageStatus, "message_status"),
    ):
        assert model.__name__ in app.models.__all__
        assert model.__tablename__ == table_name
        assert model.__table__ is Base.metadata.tables[table_name]


def test_migrations_match_the_models(migrated_engine: sa.Engine) -> None:
    """The migrations must produce exactly the schema the models describe.

    Previously this diffed the metadata against an empty database, which was
    only meaningful while there were no models. Now it compares against a
    migrated database, so it fails if a model is changed without a migration
    (or vice versa) -- the same drift `alembic check` catches, enforced by the
    suite.
    """
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)

    assert diff == [], f"models and migrations disagree: {diff}"


def test_migration_history_has_a_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    # Multiple heads mean branched history that "alembic upgrade head" cannot
    # resolve; catching it here is cheaper than at deploy time.
    assert len(script.get_heads()) == 1


def test_alembic_ini_does_not_hard_code_a_database_url() -> None:
    # The URL must come from app.core.config so the app and migrations cannot
    # drift onto different databases.
    assert not _alembic_config().get_main_option("sqlalchemy.url", default="")


def test_the_index_set_is_exactly_what_the_audit_justified(
    migrated_engine: sa.Engine,
) -> None:
    """Pins every explicit index, so gaps and redundancy both show up here.

    Each entry earns its place against a real access pattern; primary keys and
    unique constraints already supply their own indexes and are not repeated.
    Deliberately absent: a plain messages.conversation_id index (the composite
    covers the prefix and the ordering), and separate indexes on
    message_status.message_id or conversation_participants.conversation_id
    (covered by the unique constraint and the composite primary key).
    """
    inspector = sa.inspect(migrated_engine)
    actual = {
        table: sorted(ix["name"] for ix in inspector.get_indexes(table))
        for table in inspector.get_table_names()
        if table != "alembic_version"
    }

    assert actual == {
        # Reverse lookup "who saved me", and the ON DELETE CASCADE sweep.
        "contacts": ["ix_contacts_contact_user_id"],
        # "every conversation this user is in" -- the conversation list.
        "conversation_participants": ["ix_conversation_participants_user_id"],
        "conversations": [],
        # Backs the RESTRICT check when a user deletion is attempted.
        "message_status": ["ix_message_status_user_id"],
        "messages": [
            # Filter and ORDER BY together for the history query.
            "ix_messages_conversation_id_created_at",
            # The replies relationship and the SET NULL sweep.
            "ix_messages_reply_to_id",
            # Backs the RESTRICT check.
            "ix_messages_sender_id",
        ],
        # Every live session for one user, for revoke-all on password change.
        "refresh_tokens": ["ix_refresh_tokens_user_id"],
        "users": [],
    }


def test_every_foreign_key_has_a_deliberate_delete_rule(
    migrated_engine: sa.Engine,
) -> None:
    """No foreign key may fall back to the default NO ACTION.

    Each rule is a decision: CASCADE where the parent owns the child, RESTRICT
    where deleting would destroy history, SET NULL where the reference is
    optional context.
    """
    inspector = sa.inspect(migrated_engine)
    actual = {
        (table, fk["constrained_columns"][0]): fk["options"].get("ondelete")
        for table in inspector.get_table_names()
        if table != "alembic_version"
        for fk in inspector.get_foreign_keys(table)
    }

    assert actual == {
        ("contacts", "user_id"): "CASCADE",
        ("contacts", "contact_user_id"): "CASCADE",
        ("conversation_participants", "conversation_id"): "CASCADE",
        ("conversation_participants", "user_id"): "RESTRICT",
        # The read pointer is optional context: clear it, keep the membership.
        ("conversation_participants", "last_read_message_id"): "SET NULL",
        # A session is not history. An account that goes away takes its live
        # sessions with it rather than being blocked by them.
        ("refresh_tokens", "user_id"): "CASCADE",
        ("messages", "conversation_id"): "CASCADE",
        ("messages", "sender_id"): "RESTRICT",
        ("messages", "reply_to_id"): "SET NULL",
        ("message_status", "message_id"): "CASCADE",
        ("message_status", "user_id"): "RESTRICT",
    }
