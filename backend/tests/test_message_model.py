"""Database behaviour of Message and MessageStatus."""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    ConversationType,
    DeliveryStatus,
    Message,
    MessageStatus,
    MessageType,
    User,
)


@pytest.fixture
def users(db_session: Session) -> dict[str, User]:
    created = {
        name: User(username=name, display_name=name.title(), password_hash="hash")
        for name in ("alice", "bob")
    }
    db_session.add_all(created.values())
    db_session.commit()
    return created


@pytest.fixture
def conversation(db_session: Session) -> Conversation:
    conversation = Conversation(type=ConversationType.DIRECT)
    db_session.add(conversation)
    db_session.commit()
    return conversation


@pytest.fixture
def message(db_session: Session, users: dict[str, User], conversation: Conversation) -> Message:
    message = Message(
        conversation_id=conversation.id,
        sender_id=users["alice"].id,
        content="hello",
        message_type=MessageType.TEXT,
    )
    db_session.add(message)
    db_session.commit()
    return message


def count(db_session: Session, model: type) -> int:
    db_session.expire_all()
    return db_session.scalar(sa.select(sa.func.count()).select_from(model))


# --- Message ---------------------------------------------------------------


def test_a_message_can_be_sent(db_session: Session, message: Message) -> None:
    stored = db_session.scalars(sa.select(Message)).one()

    assert stored.id is not None
    assert stored.content == "hello"
    assert stored.message_type is MessageType.TEXT


@pytest.mark.parametrize("missing", ["conversation_id", "sender_id", "content", "message_type"])
def test_required_message_fields_are_rejected_when_missing(
    db_session: Session, users: dict[str, User], conversation: Conversation, missing: str
) -> None:
    message = Message(
        conversation_id=conversation.id,
        sender_id=users["alice"].id,
        content="hi",
        message_type=MessageType.TEXT,
    )
    setattr(message, missing, None)
    db_session.add(message)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_message_type_persists_as_its_enum_value(db_session: Session, message: Message) -> None:
    db_session.expire_all()

    assert db_session.execute(sa.text("select message_type from messages")).scalar() == "text"
    assert db_session.scalars(sa.select(Message)).one().message_type is MessageType.TEXT


def test_created_at_is_populated_as_aware_utc(db_session: Session, message: Message) -> None:
    db_session.expire_all()
    created_at = db_session.scalars(sa.select(Message)).one().created_at

    assert created_at.utcoffset() == timedelta(0)
    assert created_at <= datetime.now(timezone.utc)


def test_edited_at_and_expires_at_default_to_null(db_session: Session, message: Message) -> None:
    db_session.expire_all()
    stored = db_session.scalars(sa.select(Message)).one()

    assert stored.edited_at is None
    assert stored.expires_at is None


def test_edited_at_and_expires_at_round_trip(
    db_session: Session, users: dict[str, User], conversation: Conversation
) -> None:
    moment = datetime(2026, 5, 6, 7, 8, 9, 123456, tzinfo=timezone.utc)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["alice"].id,
            content="edited",
            message_type=MessageType.TEXT,
            edited_at=moment,
            expires_at=moment,
        )
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(sa.select(Message)).one()
    assert stored.edited_at == moment
    assert stored.expires_at == moment


def test_the_model_does_not_validate_content(
    db_session: Session, users: dict[str, User], conversation: Conversation
) -> None:
    """SERVICE-LAYER RULE: rejecting empty content is not the model's job."""
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["alice"].id,
            content="",
            message_type=MessageType.TEXT,
        )
    )
    db_session.commit()

    assert count(db_session, Message) == 1


# --- Message relationships -------------------------------------------------


def test_message_navigates_to_conversation_and_sender(
    db_session: Session, message: Message
) -> None:
    db_session.expire_all()
    stored = db_session.scalars(sa.select(Message)).one()

    assert stored.conversation.type is ConversationType.DIRECT
    assert stored.sender.username == "alice"


def test_conversation_exposes_its_messages(db_session: Session, message: Message) -> None:
    db_session.expire_all()
    conversation = db_session.scalars(sa.select(Conversation)).one()

    assert [m.content for m in conversation.messages] == ["hello"]


def test_user_exposes_sent_messages(db_session: Session, message: Message) -> None:
    db_session.expire_all()
    alice = db_session.scalars(sa.select(User).where(User.username == "alice")).one()

    assert [m.content for m in alice.sent_messages] == ["hello"]


# --- replies ---------------------------------------------------------------


def test_a_message_can_reply_to_another(
    db_session: Session, users: dict[str, User], conversation: Conversation, message: Message
) -> None:
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["bob"].id,
            content="hi back",
            message_type=MessageType.TEXT,
            reply_to_id=message.id,
        )
    )
    db_session.commit()
    db_session.expire_all()

    original = db_session.get(Message, message.id)
    reply = db_session.scalars(sa.select(Message).where(Message.content == "hi back")).one()

    assert reply.reply_to is not None and reply.reply_to.id == original.id
    assert [r.content for r in original.replies] == ["hi back"]


def test_reply_to_is_optional(db_session: Session, message: Message) -> None:
    db_session.expire_all()
    stored = db_session.scalars(sa.select(Message)).one()

    assert stored.reply_to_id is None
    assert stored.reply_to is None
    assert stored.replies == []


# --- foreign keys ----------------------------------------------------------


def test_message_with_an_unknown_conversation_is_rejected(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add(
        Message(
            conversation_id=999_999,
            sender_id=users["alice"].id,
            content="x",
            message_type=MessageType.TEXT,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_message_with_an_unknown_sender_is_rejected(
    db_session: Session, conversation: Conversation
) -> None:
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=999_999,
            content="x",
            message_type=MessageType.TEXT,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_message_replying_to_an_unknown_message_is_rejected(
    db_session: Session, users: dict[str, User], conversation: Conversation
) -> None:
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["alice"].id,
            content="x",
            message_type=MessageType.TEXT,
            reply_to_id=999_999,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- deletion --------------------------------------------------------------


def test_deleting_a_conversation_deletes_its_messages_and_statuses(
    db_session: Session, users: dict[str, User], conversation: Conversation, message: Message
) -> None:
    """Two-level cascade: conversation -> messages -> message_status."""
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
        )
    )
    db_session.commit()

    db_session.execute(sa.text("delete from conversations where id = :i"), {"i": conversation.id})
    db_session.commit()

    assert count(db_session, Message) == 0
    assert count(db_session, MessageStatus) == 0
    assert count(db_session, User) == 2, "users are untouched"


def test_deleting_a_conversation_works_even_when_it_contains_replies(
    db_session: Session, users: dict[str, User], conversation: Conversation, message: Message
) -> None:
    """Self-referencing rows must not block the conversation cascade.

    With RESTRICT on reply_to_id this would fail: the cascade would try to
    delete a message another message still points at. SET NULL is what keeps
    a conversation containing replies deletable.
    """
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["bob"].id,
            content="reply",
            message_type=MessageType.TEXT,
            reply_to_id=message.id,
        )
    )
    db_session.commit()

    db_session.execute(sa.text("delete from conversations where id = :i"), {"i": conversation.id})
    db_session.commit()

    assert count(db_session, Message) == 0


def test_deleting_a_message_preserves_its_replies(
    db_session: Session, users: dict[str, User], conversation: Conversation, message: Message
) -> None:
    """A reply is history: it survives, with its pointer cleared."""
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=users["bob"].id,
            content="reply",
            message_type=MessageType.TEXT,
            reply_to_id=message.id,
        )
    )
    db_session.commit()

    db_session.execute(sa.text("delete from messages where id = :i"), {"i": message.id})
    db_session.commit()
    db_session.expire_all()

    surviving = db_session.scalars(sa.select(Message)).one()
    assert surviving.content == "reply"
    assert surviving.reply_to_id is None


def test_deleting_a_message_deletes_its_statuses(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add_all(
        [
            MessageStatus(
                message_id=message.id, user_id=users["alice"].id, status=DeliveryStatus.SENT
            ),
            MessageStatus(
                message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.READ
            ),
        ]
    )
    db_session.commit()

    db_session.execute(sa.text("delete from messages where id = :i"), {"i": message.id})
    db_session.commit()

    assert count(db_session, MessageStatus) == 0


# --- user deletion ---------------------------------------------------------


def test_deleting_a_user_who_has_sent_messages_is_refused(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    """DATABASE INVARIANT: sender_id is RESTRICT, so history cannot vanish."""
    db_session.delete(users["alice"])
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    assert count(db_session, Message) == 1


def test_deleting_a_user_with_status_rows_is_refused(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    """DATABASE INVARIANT: message_status.user_id is RESTRICT too."""
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.DELIVERED
        )
    )
    db_session.commit()

    db_session.delete(users["bob"])
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    assert count(db_session, MessageStatus) == 1


def test_no_path_from_user_deletion_destroys_messages(migrated_engine: sa.Engine) -> None:
    """No foreign key from users into message history may cascade."""
    inspector = sa.inspect(migrated_engine)

    for table in ("messages", "message_status"):
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] == "users":
                assert fk["options"].get("ondelete") == "RESTRICT", (
                    f"{table}.{fk['constrained_columns']} would destroy history"
                )


# --- MessageStatus ---------------------------------------------------------


@pytest.mark.parametrize(
    "status", [DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.READ]
)
def test_each_delivery_status_persists(
    db_session: Session, users: dict[str, User], message: Message, status: DeliveryStatus
) -> None:
    db_session.add(
        MessageStatus(message_id=message.id, user_id=users["bob"].id, status=status)
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(sa.select(MessageStatus)).one()
    assert stored.status is status
    assert db_session.execute(sa.text("select status from message_status")).scalar() == (
        status.value
    )


def test_status_updated_at_is_populated_as_aware_utc(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(MessageStatus)).one().updated_at.utcoffset() == (
        timedelta(0)
    )


def test_status_updated_at_advances_when_the_status_changes(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
        )
    )
    db_session.commit()
    original = db_session.scalars(sa.select(MessageStatus)).one().updated_at

    db_session.scalars(sa.select(MessageStatus)).one().status = DeliveryStatus.READ
    db_session.commit()
    db_session.expire_all()

    assert db_session.scalars(sa.select(MessageStatus)).one().updated_at > original


def test_status_navigates_to_message_and_user(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
        )
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(sa.select(MessageStatus)).one()
    assert stored.message.content == "hello"
    assert stored.user.username == "bob"


def test_message_exposes_its_statuses(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add_all(
        [
            MessageStatus(
                message_id=message.id, user_id=users["alice"].id, status=DeliveryStatus.SENT
            ),
            MessageStatus(
                message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.READ
            ),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.get(Message, message.id)
    assert {s.user.username: s.status for s in stored.statuses} == {
        "alice": DeliveryStatus.SENT,
        "bob": DeliveryStatus.READ,
    }


def test_one_status_row_per_message_and_user(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    """DATABASE INVARIANT: enforced by the unique constraint on the pair."""
    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
        )
    )
    db_session.commit()

    db_session.add(
        MessageStatus(
            message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.READ
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_users_may_have_status_for_the_same_message(
    db_session: Session, users: dict[str, User], message: Message
) -> None:
    db_session.add_all(
        [
            MessageStatus(
                message_id=message.id, user_id=users["alice"].id, status=DeliveryStatus.SENT
            ),
            MessageStatus(
                message_id=message.id, user_id=users["bob"].id, status=DeliveryStatus.SENT
            ),
        ]
    )
    db_session.commit()

    assert count(db_session, MessageStatus) == 2


def test_status_with_an_unknown_message_is_rejected(
    db_session: Session, users: dict[str, User]
) -> None:
    db_session.add(
        MessageStatus(message_id=999_999, user_id=users["alice"].id, status=DeliveryStatus.SENT)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_status_with_an_unknown_user_is_rejected(
    db_session: Session, message: Message
) -> None:
    db_session.add(
        MessageStatus(message_id=message.id, user_id=999_999, status=DeliveryStatus.SENT)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- schema ----------------------------------------------------------------


def test_message_foreign_key_delete_rules(migrated_engine: sa.Engine) -> None:
    rules = {
        fk["referred_table"]: fk["options"].get("ondelete")
        for fk in sa.inspect(migrated_engine).get_foreign_keys("messages")
    }

    assert rules == {"conversations": "CASCADE", "users": "RESTRICT", "messages": "SET NULL"}


def test_message_status_foreign_key_delete_rules(migrated_engine: sa.Engine) -> None:
    rules = {
        fk["referred_table"]: fk["options"].get("ondelete")
        for fk in sa.inspect(migrated_engine).get_foreign_keys("message_status")
    }

    assert rules == {"messages": "CASCADE", "users": "RESTRICT"}


def test_history_query_is_supported_by_a_composite_index(migrated_engine: sa.Engine) -> None:
    """WHERE conversation_id = ? ORDER BY created_at needs both columns."""
    indexes = {
        ix["name"]: ix["column_names"]
        for ix in sa.inspect(migrated_engine).get_indexes("messages")
    }

    assert indexes.get("ix_messages_conversation_id_created_at") == [
        "conversation_id",
        "created_at",
    ]


def test_message_status_pair_is_unique(migrated_engine: sa.Engine) -> None:
    constraints = sa.inspect(migrated_engine).get_unique_constraints("message_status")

    assert [c["column_names"] for c in constraints] == [["message_id", "user_id"]]
