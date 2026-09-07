"""Database behaviour of the Contact model and its self-referential links."""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Contact, User


def make_user(username: str) -> User:
    return User(username=username, display_name=username.title(), password_hash="hash")


@pytest.fixture
def users(db_session: Session) -> dict[str, User]:
    """Three saved users, addressable by name."""
    created = {name: make_user(name) for name in ("a", "b", "c")}
    db_session.add_all(created.values())
    db_session.commit()
    return created


def contact_pairs(db_session: Session) -> set[tuple[int, int]]:
    """Every contact row as (user_id, contact_user_id), read from the database."""
    db_session.expire_all()
    return set(db_session.execute(sa.select(Contact.user_id, Contact.contact_user_id)).all())


# --- creation --------------------------------------------------------------


def test_a_user_can_save_another_user_as_a_contact(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    db_session.commit()

    assert contact_pairs(db_session) == {(users["a"].id, users["b"].id)}


def test_created_at_is_populated_as_aware_utc(
    db_session: Session, users: dict[str, User]
) -> None:
    before = datetime.now(timezone.utc)
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    db_session.commit()
    db_session.expire_all()

    contact = db_session.scalars(sa.select(Contact)).one()

    assert contact.created_at.tzinfo is not None
    assert contact.created_at.utcoffset() == timedelta(0)
    assert before - timedelta(seconds=5) <= contact.created_at <= datetime.now(timezone.utc)


def test_contact_has_no_updated_at() -> None:
    """A contact records that a link was made; it is not an editable entity."""
    assert "updated_at" not in Contact.__table__.columns


# --- duplicates ------------------------------------------------------------


def test_the_same_contact_cannot_be_added_twice(
    db_session: Session, users: dict[str, User]
) -> None:
    """DATABASE INVARIANT: enforced by the composite primary key."""
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    db_session.commit()

    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_no_redundant_unique_constraint_over_the_primary_key(
    migrated_engine: sa.Engine,
) -> None:
    # The composite primary key already provides the uniqueness; a unique
    # constraint on the same columns would just duplicate its index.
    assert sa.inspect(migrated_engine).get_unique_constraints("contacts") == []


# --- direction -------------------------------------------------------------


def test_contacts_are_directed_so_both_directions_may_coexist(
    db_session: Session, users: dict[str, User]
) -> None:
    """A saving B and B saving A are independent rows, not one mutual link."""
    db_session.add_all(
        [
            Contact(user_id=users["a"].id, contact_user_id=users["b"].id),
            Contact(user_id=users["b"].id, contact_user_id=users["a"].id),
        ]
    )
    db_session.commit()

    assert contact_pairs(db_session) == {
        (users["a"].id, users["b"].id),
        (users["b"].id, users["a"].id),
    }


# --- referential integrity -------------------------------------------------


def test_contact_referencing_a_nonexistent_user_is_rejected(
    db_session: Session, users: dict[str, User]
) -> None:
    """DATABASE INVARIANT: relies on SQLite foreign-key enforcement (A02.1)."""
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=999_999))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_self_contact_is_not_blocked_by_the_database(
    db_session: Session, users: dict[str, User]
) -> None:
    """APPLICATION POLICY, not a database invariant -- and currently unenforced.

    "A user cannot add themselves" is a product rule. No CHECK constraint
    implements it, so the database accepts the row today. This test documents
    the real current behaviour rather than implying a guard that does not
    exist. The Contacts service in a later stage must reject it; when that
    service arrives this test should be replaced by one asserting the service
    refuses the request.
    """
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["a"].id))
    db_session.commit()

    assert contact_pairs(db_session) == {(users["a"].id, users["a"].id)}


# --- deletion --------------------------------------------------------------


def test_deleting_a_user_removes_contacts_they_own(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add_all(
        [
            Contact(user_id=users["a"].id, contact_user_id=users["b"].id),
            Contact(user_id=users["a"].id, contact_user_id=users["c"].id),
        ]
    )
    db_session.commit()

    db_session.delete(users["a"])
    db_session.commit()

    assert contact_pairs(db_session) == set()


def test_deleting_a_user_removes_contacts_pointing_at_them(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add_all(
        [
            Contact(user_id=users["b"].id, contact_user_id=users["a"].id),
            Contact(user_id=users["c"].id, contact_user_id=users["a"].id),
        ]
    )
    db_session.commit()

    db_session.delete(users["a"])
    db_session.commit()

    assert contact_pairs(db_session) == set()


def test_deleting_a_user_leaves_unrelated_users_and_contacts_intact(
    db_session: Session, users: dict[str, User]
) -> None:
    a, b, c = users["a"].id, users["b"].id, users["c"].id
    db_session.add_all(
        [
            Contact(user_id=a, contact_user_id=b),
            Contact(user_id=b, contact_user_id=a),
            Contact(user_id=c, contact_user_id=a),
            Contact(user_id=a, contact_user_id=c),
            Contact(user_id=b, contact_user_id=c),  # involves neither side of A
        ]
    )
    db_session.commit()

    db_session.delete(users["a"])
    db_session.commit()

    # Only rows mentioning A disappear.
    assert contact_pairs(db_session) == {(b, c)}

    remaining = set(db_session.scalars(sa.select(User.username)).all())
    assert remaining == {"b", "c"}


def test_database_cascade_applies_without_the_orm(
    db_session: Session, users: dict[str, User]
) -> None:
    """The cascade must be in the database, not only in relationship config.

    A raw DELETE bypasses SQLAlchemy's relationship machinery entirely, so this
    fails if integrity depended on the ORM.
    """
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    db_session.commit()

    db_session.execute(sa.text("delete from users where id = :id"), {"id": users["a"].id})
    db_session.commit()

    assert contact_pairs(db_session) == set()


# --- ORM relationships -----------------------------------------------------


def test_owner_relationship_exposes_saved_contacts(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add(Contact(user_id=users["a"].id, contact_user_id=users["b"].id))
    db_session.commit()
    db_session.expire_all()

    a = db_session.scalars(sa.select(User).where(User.username == "a")).one()

    assert [c.contact_user.username for c in a.contacts] == ["b"]
    assert a.contact_of == []


def test_reverse_relationship_exposes_users_who_saved_this_user(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add_all(
        [
            Contact(user_id=users["b"].id, contact_user_id=users["a"].id),
            Contact(user_id=users["c"].id, contact_user_id=users["a"].id),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    a = db_session.scalars(sa.select(User).where(User.username == "a")).one()

    assert sorted(c.owner.username for c in a.contact_of) == ["b", "c"]
    assert a.contacts == []


def test_the_two_relationships_use_different_foreign_keys(
    db_session: Session, users: dict[str, User]
) -> None:
    """Guards against both relationships collapsing onto the same foreign key."""
    db_session.add_all(
        [
            Contact(user_id=users["a"].id, contact_user_id=users["b"].id),
            Contact(user_id=users["c"].id, contact_user_id=users["a"].id),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    a = db_session.scalars(sa.select(User).where(User.username == "a")).one()

    assert [c.contact_user.username for c in a.contacts] == ["b"]
    assert [c.owner.username for c in a.contact_of] == ["c"]


# --- schema ----------------------------------------------------------------


def test_migration_creates_the_expected_contacts_schema(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)

    assert "contacts" in inspector.get_table_names()
    assert {c["name"] for c in inspector.get_columns("contacts")} == {
        "user_id",
        "contact_user_id",
        "created_at",
    }

    pk = inspector.get_pk_constraint("contacts")
    assert pk["name"] == "pk_contacts"
    assert pk["constrained_columns"] == ["user_id", "contact_user_id"]


def test_both_foreign_keys_cascade_on_delete(migrated_engine: sa.Engine) -> None:
    foreign_keys = {
        fk["name"]: fk for fk in sa.inspect(migrated_engine).get_foreign_keys("contacts")
    }

    assert set(foreign_keys) == {
        "fk_contacts_user_id_users",
        "fk_contacts_contact_user_id_users",
    }
    for fk in foreign_keys.values():
        assert fk["referred_table"] == "users"
        assert fk["options"].get("ondelete") == "CASCADE"
