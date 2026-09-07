"""Database behaviour of the User model."""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models import User


def make_user(**overrides: object) -> User:
    """A valid user, with fields overridable per test."""
    values: dict[str, object] = {
        "username": "alice",
        "display_name": "Alice",
        "password_hash": "$2b$12$abcdefghijklmnopqrstuv",
    }
    values.update(overrides)
    return User(**values)


# --- creation --------------------------------------------------------------


def test_a_valid_user_can_be_inserted_and_retrieved(db_session: Session) -> None:
    db_session.add(make_user(phone_number="+15550001", avatar_url="https://example.com/a.png"))
    db_session.commit()

    user = db_session.scalars(sa.select(User).where(User.username == "alice")).one()

    assert user.id is not None
    assert user.username == "alice"
    assert user.display_name == "Alice"
    assert user.phone_number == "+15550001"
    assert user.avatar_url == "https://example.com/a.png"


def test_optional_fields_may_be_omitted(db_session: Session) -> None:
    db_session.add(make_user())
    db_session.commit()

    user = db_session.scalars(sa.select(User)).one()

    assert user.phone_number is None
    assert user.avatar_url is None
    assert user.last_seen is None


# --- required fields -------------------------------------------------------


@pytest.mark.parametrize("missing", ["username", "display_name", "password_hash"])
def test_missing_required_field_is_rejected(db_session: Session, missing: str) -> None:
    user = make_user()
    setattr(user, missing, None)
    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- uniqueness ------------------------------------------------------------


def test_username_must_be_unique(db_session: Session) -> None:
    db_session.add(make_user(username="alice"))
    db_session.commit()

    db_session.add(make_user(username="alice"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_phone_number_must_be_unique_when_present(db_session: Session) -> None:
    db_session.add(make_user(username="alice", phone_number="+15550001"))
    db_session.commit()

    db_session.add(make_user(username="bob", phone_number="+15550001"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_many_users_may_have_no_phone_number(db_session: Session) -> None:
    """A UNIQUE column must not collapse users who share a NULL phone number.

    SQL treats NULLs as distinct in a unique constraint, so this works without a
    partial index -- but it is the kind of thing that must be proven, not
    assumed, because getting it wrong allows exactly one phoneless account.
    """
    for name in ("alice", "bob", "carol"):
        db_session.add(make_user(username=name, phone_number=None))
    db_session.commit()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(User)) == 3


# --- defaults --------------------------------------------------------------


def test_new_user_defaults_to_offline(db_session: Session) -> None:
    db_session.add(make_user())
    db_session.commit()

    user = db_session.scalars(sa.select(User)).one()

    assert user.is_online is False


def test_timestamps_are_populated_on_insert(db_session: Session) -> None:
    before = datetime.now(timezone.utc)
    db_session.add(make_user())
    db_session.commit()

    user = db_session.scalars(sa.select(User)).one()

    assert user.created_at is not None
    assert user.updated_at is not None
    assert before - timedelta(seconds=5) <= user.created_at <= datetime.now(timezone.utc)


# --- timestamp conventions -------------------------------------------------


def test_timestamps_come_back_as_aware_utc(db_session: Session) -> None:
    db_session.add(make_user())
    db_session.commit()
    db_session.expire_all()

    user = db_session.scalars(sa.select(User)).one()

    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)


def test_updated_at_advances_on_update(db_session: Session) -> None:
    db_session.add(make_user())
    db_session.commit()
    user = db_session.scalars(sa.select(User)).one()
    original = user.updated_at

    user.display_name = "Alice B"
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(User)).one().updated_at > original


# --- last_seen -------------------------------------------------------------


def test_last_seen_is_optional(db_session: Session) -> None:
    db_session.add(make_user())
    db_session.commit()

    assert db_session.scalars(sa.select(User)).one().last_seen is None


def test_last_seen_round_trips_as_aware_utc(db_session: Session) -> None:
    seen = datetime(2026, 3, 4, 5, 6, 7, 123456, tzinfo=timezone.utc)
    db_session.add(make_user(last_seen=seen))
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(sa.select(User)).one().last_seen

    assert stored == seen
    assert stored is not None and stored.microsecond == 123456, "sub-second precision kept"


def test_naive_last_seen_is_rejected(db_session: Session) -> None:
    """UtcDateTime refuses ambiguous input rather than guessing a zone."""
    db_session.add(make_user(last_seen=datetime(2026, 3, 4, 5, 6, 7)))

    with pytest.raises(StatementError):
        db_session.commit()


def test_presence_is_not_managed_by_the_model(db_session: Session) -> None:
    """Editing a user must not silently change presence.

    Presence belongs to the service and WebSocket layers. If the model ever
    grew an onupdate hook for these columns, an unrelated profile edit would
    quietly mark someone online or move their last-seen time.
    """
    seen = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db_session.add(make_user(is_online=True, last_seen=seen))
    db_session.commit()

    user = db_session.scalars(sa.select(User)).one()
    user.display_name = "Changed"
    db_session.commit()
    db_session.expire_all()

    refreshed = db_session.scalars(sa.select(User)).one()
    assert refreshed.is_online is True
    assert refreshed.last_seen == seen


# --- password hash ---------------------------------------------------------


def test_password_hash_is_stored_verbatim(db_session: Session) -> None:
    """The model stores whatever hash it is given.

    Hashing and verification are the service layer's job; this only checks that
    the column holds the value unchanged. Nothing here should be read as a hint
    that hashing belongs on the model.
    """
    digest = "$2b$12$K1x8s0Nq5rTf9uVwXyZaBu"
    db_session.add(make_user(password_hash=digest))
    db_session.commit()

    assert db_session.scalars(sa.select(User)).one().password_hash == digest


def test_model_exposes_no_password_handling(db_session: Session) -> None:
    for attribute in ("set_password", "check_password", "verify_password", "password"):
        assert not hasattr(User, attribute), f"User should not define {attribute}"


# --- schema produced by the migration --------------------------------------


def test_migration_creates_the_expected_users_schema(migrated_engine: sa.Engine) -> None:
    """The schema under test is built by Alembic, not by create_all."""
    inspector = sa.inspect(migrated_engine)

    assert "users" in inspector.get_table_names()

    columns = {c["name"]: c for c in inspector.get_columns("users")}
    assert set(columns) == {
        "id",
        "username",
        "phone_number",
        "display_name",
        "avatar_url",
        "password_hash",
        "is_online",
        "last_seen",
        "created_at",
        "updated_at",
    }

    required = {"username", "display_name", "password_hash", "is_online",
                "created_at", "updated_at"}
    for name, column in columns.items():
        assert column["nullable"] is (name not in required | {"id"}), name


def test_migration_names_constraints_by_convention(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)

    assert inspector.get_pk_constraint("users")["name"] == "pk_users"
    unique = {c["name"] for c in inspector.get_unique_constraints("users")}
    assert unique == {"uq_users_username", "uq_users_phone_number"}


def test_users_table_can_be_downgraded_and_recreated(
    migrated_engine: sa.Engine, alembic_config: Config
) -> None:
    assert "users" in sa.inspect(migrated_engine).get_table_names()

    command.downgrade(alembic_config, "base")
    assert "users" not in sa.inspect(migrated_engine).get_table_names()

    command.upgrade(alembic_config, "head")
    assert "users" in sa.inspect(migrated_engine).get_table_names()
