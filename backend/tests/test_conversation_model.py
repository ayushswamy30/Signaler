"""Database behaviour of Conversation and ConversationParticipant."""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    ConversationParticipant,
    ConversationType,
    ParticipantRole,
    User,
)


@pytest.fixture
def users(db_session: Session) -> dict[str, User]:
    created = {
        name: User(username=name, display_name=name.title(), password_hash="hash")
        for name in ("alice", "bob", "carol")
    }
    db_session.add_all(created.values())
    db_session.commit()
    return created


@pytest.fixture
def group(db_session: Session) -> Conversation:
    conversation = Conversation(type=ConversationType.GROUP, name="Team")
    db_session.add(conversation)
    db_session.commit()
    return conversation


# --- Conversation ----------------------------------------------------------


def test_a_direct_conversation_can_be_created_without_a_name(db_session: Session) -> None:
    db_session.add(Conversation(type=ConversationType.DIRECT))
    db_session.commit()

    conversation = db_session.scalars(sa.select(Conversation)).one()

    assert conversation.id is not None
    assert conversation.type is ConversationType.DIRECT
    assert conversation.name is None
    assert conversation.avatar_url is None


def test_a_group_conversation_can_carry_a_name_and_avatar(db_session: Session) -> None:
    db_session.add(
        Conversation(
            type=ConversationType.GROUP,
            name="Weekend Plans",
            avatar_url="https://example.com/g.png",
        )
    )
    db_session.commit()

    conversation = db_session.scalars(sa.select(Conversation)).one()

    assert conversation.type is ConversationType.GROUP
    assert conversation.name == "Weekend Plans"
    assert conversation.avatar_url == "https://example.com/g.png"


def test_conversation_type_is_required(db_session: Session) -> None:
    db_session.add(Conversation(name="no type"))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_conversation_type_persists_as_its_enum_value(db_session: Session) -> None:
    db_session.add(Conversation(type=ConversationType.GROUP, name="Team"))
    db_session.commit()
    db_session.expire_all()

    stored = db_session.execute(sa.text("select type from conversations")).scalar()

    assert stored == "group", "the member value is stored, not the member name"
    assert db_session.scalars(sa.select(Conversation)).one().type is ConversationType.GROUP


def test_conversation_timestamps_are_populated_as_aware_utc(db_session: Session) -> None:
    before = datetime.now(timezone.utc)
    db_session.add(Conversation(type=ConversationType.DIRECT))
    db_session.commit()
    db_session.expire_all()

    conversation = db_session.scalars(sa.select(Conversation)).one()

    assert conversation.created_at.utcoffset() == timedelta(0)
    assert conversation.updated_at.utcoffset() == timedelta(0)
    assert before - timedelta(seconds=5) <= conversation.created_at <= datetime.now(timezone.utc)


def test_the_schema_does_not_encode_conversation_shape_rules(db_session: Session) -> None:
    """SERVICE-LAYER INVARIANTS, deliberately not database constraints.

    A direct conversation with no participants, or a group with no name, is
    accepted by the schema. Enforcing those in the database would make
    ordinary steps impossible -- a conversation has to exist before its
    participants can reference it. The service layer owns these rules.
    """
    db_session.add_all(
        [
            Conversation(type=ConversationType.GROUP),  # group with no name
            Conversation(type=ConversationType.DIRECT, name="named direct"),
        ]
    )
    db_session.commit()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(Conversation)) == 2


def test_two_direct_conversations_between_the_same_pair_are_not_blocked(
    db_session: Session, users: dict[str, User]
) -> None:
    """SERVICE-LAYER INVARIANT, not a database constraint -- and unenforced.

    Participants live in a child table, so no column constraint can express
    "this exact pair already has a direct conversation". The schema therefore
    permits duplicates today, and this test records that honestly rather than
    implying a guard that does not exist.

    The future ConversationService must look for an existing DIRECT
    conversation containing exactly these two users before creating one.
    """
    for _ in range(2):
        conversation = Conversation(type=ConversationType.DIRECT)
        db_session.add(conversation)
        db_session.flush()
        db_session.add_all(
            [
                ConversationParticipant(
                    conversation_id=conversation.id, user_id=users["alice"].id
                ),
                ConversationParticipant(
                    conversation_id=conversation.id, user_id=users["bob"].id
                ),
            ]
        )
    db_session.commit()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(Conversation)) == 2


# --- ConversationParticipant ----------------------------------------------


def test_a_user_can_join_a_conversation(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()

    participant = db_session.scalars(sa.select(ConversationParticipant)).one()

    assert participant.conversation_id == group.id
    assert participant.user_id == users["alice"].id


def test_role_defaults_to_member(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(ConversationParticipant)).one().role is (
        ParticipantRole.MEMBER
    )


def test_admin_role_persists(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(
            conversation_id=group.id, user_id=users["alice"].id, role=ParticipantRole.ADMIN
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.execute(
        sa.text("select role from conversation_participants")
    ).scalar() == "admin"
    assert db_session.scalars(sa.select(ConversationParticipant)).one().role is (
        ParticipantRole.ADMIN
    )


def test_joined_at_is_populated_as_aware_utc(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()
    db_session.expire_all()

    joined_at = db_session.scalars(sa.select(ConversationParticipant)).one().joined_at

    assert joined_at.utcoffset() == timedelta(0)


# --- read state ------------------------------------------------------------


def test_last_read_message_id_defaults_to_null(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(ConversationParticipant)).one().last_read_message_id is None


def test_last_read_message_id_stores_an_integer_without_a_messages_table(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    """It is a bare integer until the Message model exists.

    No foreign key constrains it yet, so an arbitrary value is accepted. A
    later migration adds the reference to messages.id.
    """
    db_session.add(
        ConversationParticipant(
            conversation_id=group.id, user_id=users["alice"].id, last_read_message_id=42
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(ConversationParticipant)).one().last_read_message_id == 42


def test_no_messages_table_exists_yet(migrated_engine: sa.Engine) -> None:
    assert "messages" not in sa.inspect(migrated_engine).get_table_names()


def test_last_read_message_id_has_no_foreign_key_yet(migrated_engine: sa.Engine) -> None:
    referenced = {
        fk["referred_table"]
        for fk in sa.inspect(migrated_engine).get_foreign_keys("conversation_participants")
    }
    assert referenced == {"conversations", "users"}


# --- composite key ---------------------------------------------------------


def test_two_different_users_may_join_the_same_conversation(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add_all(
        [
            ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id),
            ConversationParticipant(conversation_id=group.id, user_id=users["bob"].id),
        ]
    )
    db_session.commit()

    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ConversationParticipant)
    ) == 2


def test_a_user_cannot_join_the_same_conversation_twice(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    """DATABASE INVARIANT: enforced by the composite primary key."""
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()

    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_the_same_user_may_join_different_conversations(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    other = Conversation(type=ConversationType.DIRECT)
    db_session.add(other)
    db_session.flush()
    db_session.add_all(
        [
            ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id),
            ConversationParticipant(conversation_id=other.id, user_id=users["alice"].id),
        ]
    )
    db_session.commit()

    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ConversationParticipant)
    ) == 2


# --- referential integrity -------------------------------------------------


def test_participant_with_an_unknown_conversation_is_rejected(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=999_999, user_id=users["alice"].id)
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_participant_with_an_unknown_user_is_rejected(
    db_session: Session, group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=999_999)
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- deletion --------------------------------------------------------------


def test_deleting_a_conversation_removes_its_participants(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add_all(
        [
            ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id),
            ConversationParticipant(conversation_id=group.id, user_id=users["bob"].id),
        ]
    )
    db_session.commit()

    db_session.delete(group)
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ConversationParticipant)
    ) == 0
    # The users themselves are untouched.
    assert db_session.scalar(sa.select(sa.func.count()).select_from(User)) == 3


def test_conversation_cascade_applies_without_the_orm(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()

    db_session.execute(sa.text("delete from conversations where id = :i"), {"i": group.id})
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ConversationParticipant)
    ) == 0


def test_deleting_a_participating_user_is_refused(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    """DATABASE INVARIANT: the user foreign key is RESTRICT, not CASCADE.

    Deleting an account must not silently remove it from a conversation, which
    would erase part of that conversation's history for everyone else. The
    database refuses, so account deletion has to be handled deliberately.
    This is the intended semantics, not a limitation to work around.
    """
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()

    db_session.delete(users["alice"])
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    # The conversation and its membership survive the refused delete.
    assert db_session.scalar(sa.select(sa.func.count()).select_from(Conversation)) == 1
    assert db_session.scalar(
        sa.select(sa.func.count()).select_from(ConversationParticipant)
    ) == 1


def test_a_user_with_no_participation_can_still_be_deleted(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    """RESTRICT only blocks while membership exists."""
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()

    db_session.delete(users["carol"])  # never joined anything
    db_session.commit()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(User)) == 2


# --- relationships ---------------------------------------------------------


def test_conversation_exposes_its_participants(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add_all(
        [
            ConversationParticipant(
                conversation_id=group.id, user_id=users["alice"].id,
                role=ParticipantRole.ADMIN,
            ),
            ConversationParticipant(conversation_id=group.id, user_id=users["bob"].id),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    conversation = db_session.scalars(sa.select(Conversation)).one()

    assert sorted(p.user.username for p in conversation.participants) == ["alice", "bob"]
    roles = {p.user.username: p.role for p in conversation.participants}
    assert roles["alice"] is ParticipantRole.ADMIN
    assert roles["bob"] is ParticipantRole.MEMBER


def test_participant_navigates_to_its_conversation_and_user(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    db_session.add(
        ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id)
    )
    db_session.commit()
    db_session.expire_all()

    participant = db_session.scalars(sa.select(ConversationParticipant)).one()

    assert participant.conversation.name == "Team"
    assert participant.user.username == "alice"


def test_user_exposes_their_participation_rows(
    db_session: Session, users: dict[str, User], group: Conversation
) -> None:
    other = Conversation(type=ConversationType.DIRECT)
    db_session.add(other)
    db_session.flush()
    db_session.add_all(
        [
            ConversationParticipant(conversation_id=group.id, user_id=users["alice"].id),
            ConversationParticipant(conversation_id=other.id, user_id=users["alice"].id),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    alice = db_session.scalars(sa.select(User).where(User.username == "alice")).one()

    assert len(alice.conversation_participations) == 2
    assert {p.conversation.type for p in alice.conversation_participations} == {
        ConversationType.DIRECT,
        ConversationType.GROUP,
    }


def test_user_has_no_direct_conversations_shortcut() -> None:
    """The association object is the abstraction; it carries role and read state."""
    assert not hasattr(User, "conversations")


# --- schema ----------------------------------------------------------------


def test_migration_creates_the_expected_tables(migrated_engine: sa.Engine) -> None:
    tables = set(sa.inspect(migrated_engine).get_table_names())

    assert {"conversations", "conversation_participants"} <= tables


def test_participant_composite_primary_key(migrated_engine: sa.Engine) -> None:
    pk = sa.inspect(migrated_engine).get_pk_constraint("conversation_participants")

    assert pk["name"] == "pk_conversation_participants"
    assert pk["constrained_columns"] == ["conversation_id", "user_id"]


def test_participant_foreign_key_delete_rules(migrated_engine: sa.Engine) -> None:
    rules = {
        fk["referred_table"]: fk["options"].get("ondelete")
        for fk in sa.inspect(migrated_engine).get_foreign_keys("conversation_participants")
    }

    assert rules == {"conversations": "CASCADE", "users": "RESTRICT"}


def test_user_id_is_indexed_for_the_conversation_list_query(
    migrated_engine: sa.Engine,
) -> None:
    """The composite primary key covers conversation_id-first lookups only."""
    indexes = {
        ix["name"]: ix["column_names"]
        for ix in sa.inspect(migrated_engine).get_indexes("conversation_participants")
    }

    assert indexes.get("ix_conversation_participants_user_id") == ["user_id"]
