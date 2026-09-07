"""Integration tests across the whole model graph.

The per-model test files check one table at a time. These build a realistic
graph -- users, contacts, a direct and a group conversation, messages, replies
and delivery statuses -- and exercise it end to end, which is where
relationship ambiguity and cascade mistakes actually surface.
"""

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Contact,
    Conversation,
    ConversationParticipant,
    ConversationType,
    DeliveryStatus,
    Message,
    MessageStatus,
    MessageType,
    ParticipantRole,
    User,
)


@pytest.fixture
def graph(db_session: Session) -> dict[str, object]:
    """Users A/B/C, a direct conversation, a group, messages and statuses."""
    a, b, c = (
        User(username=n, display_name=n.upper(), password_hash="hash")
        for n in ("a", "b", "c")
    )
    db_session.add_all([a, b, c])
    db_session.flush()

    # A and B have each other as contacts; the two rows are independent.
    db_session.add_all(
        [
            Contact(user_id=a.id, contact_user_id=b.id),
            Contact(user_id=b.id, contact_user_id=a.id),
        ]
    )

    direct = Conversation(type=ConversationType.DIRECT)
    group = Conversation(type=ConversationType.GROUP, name="Team")
    db_session.add_all([direct, group])
    db_session.flush()

    db_session.add_all(
        [
            ConversationParticipant(conversation_id=direct.id, user_id=a.id),
            ConversationParticipant(conversation_id=direct.id, user_id=b.id),
            ConversationParticipant(
                conversation_id=group.id, user_id=a.id, role=ParticipantRole.ADMIN
            ),
            ConversationParticipant(conversation_id=group.id, user_id=b.id),
            ConversationParticipant(conversation_id=group.id, user_id=c.id),
        ]
    )

    first = Message(
        conversation_id=group.id, sender_id=a.id, content="hello all",
        message_type=MessageType.TEXT,
    )
    db_session.add(first)
    db_session.flush()

    reply = Message(
        conversation_id=group.id, sender_id=b.id, content="hi A",
        message_type=MessageType.TEXT, reply_to_id=first.id,
    )
    third = Message(
        conversation_id=group.id, sender_id=c.id, content="me too",
        message_type=MessageType.TEXT,
    )
    db_session.add_all([reply, third])
    db_session.flush()

    db_session.add_all(
        [
            MessageStatus(message_id=first.id, user_id=b.id, status=DeliveryStatus.READ),
            MessageStatus(message_id=first.id, user_id=c.id, status=DeliveryStatus.DELIVERED),
            MessageStatus(message_id=reply.id, user_id=a.id, status=DeliveryStatus.SENT),
        ]
    )
    db_session.commit()
    db_session.expire_all()

    return {
        "a": a.id, "b": b.id, "c": c.id,
        "direct": direct.id, "group": group.id,
        "first": first.id, "reply": reply.id, "third": third.id,
    }


def count(db_session: Session, model: type) -> int:
    db_session.expire_all()
    return db_session.scalar(sa.select(sa.func.count()).select_from(model))


# --- the graph persists and queries cleanly --------------------------------


def test_the_whole_graph_persists(db_session: Session, graph: dict) -> None:
    assert count(db_session, User) == 3
    assert count(db_session, Contact) == 2
    assert count(db_session, Conversation) == 2
    assert count(db_session, ConversationParticipant) == 5
    assert count(db_session, Message) == 3
    assert count(db_session, MessageStatus) == 3


def test_direct_and_group_conversations_coexist(db_session: Session, graph: dict) -> None:
    direct = db_session.get(Conversation, graph["direct"])
    group = db_session.get(Conversation, graph["group"])

    assert direct.type is ConversationType.DIRECT
    assert len(direct.participants) == 2
    assert direct.name is None

    assert group.type is ConversationType.GROUP
    assert len(group.participants) == 3
    assert group.name == "Team"


def test_navigating_from_a_user_to_their_messages_and_conversations(
    db_session: Session, graph: dict
) -> None:
    a = db_session.get(User, graph["a"])

    assert {p.conversation.type for p in a.conversation_participations} == {
        ConversationType.DIRECT,
        ConversationType.GROUP,
    }
    assert [m.content for m in a.sent_messages] == ["hello all"]
    assert [c.contact_user.username for c in a.contacts] == ["b"]
    assert [c.owner.username for c in a.contact_of] == ["b"]


def test_group_roles_are_readable_through_the_graph(db_session: Session, graph: dict) -> None:
    group = db_session.get(Conversation, graph["group"])

    roles = {p.user.username: p.role for p in group.participants}
    assert roles == {
        "a": ParticipantRole.ADMIN,
        "b": ParticipantRole.MEMBER,
        "c": ParticipantRole.MEMBER,
    }


def test_message_history_reads_in_creation_order(db_session: Session, graph: dict) -> None:
    history = db_session.scalars(
        sa.select(Message)
        .where(Message.conversation_id == graph["group"])
        .order_by(Message.created_at)
    ).all()

    assert [m.content for m in history] == ["hello all", "hi A", "me too"]


def test_statuses_are_reachable_from_the_message_and_the_user(
    db_session: Session, graph: dict
) -> None:
    first = db_session.get(Message, graph["first"])

    assert {s.user.username: s.status for s in first.statuses} == {
        "b": DeliveryStatus.READ,
        "c": DeliveryStatus.DELIVERED,
    }
    a = db_session.get(User, graph["a"])
    assert [s.message.content for s in a.message_statuses] == ["hi A"]


def test_reply_chain_navigates_in_both_directions(db_session: Session, graph: dict) -> None:
    first = db_session.get(Message, graph["first"])
    reply = db_session.get(Message, graph["reply"])

    assert reply.reply_to.content == "hello all"
    assert [r.content for r in first.replies] == ["hi A"]


# --- reply chain deletion --------------------------------------------------


def test_a_reply_chain_survives_deletion_of_its_root(
    db_session: Session, graph: dict
) -> None:
    """A -> B -> C: deleting A must leave both B and C intact.

    Only B's pointer is cleared; C still points at B, so the chain below the
    deleted message stays connected.
    """
    b_msg = db_session.get(Message, graph["reply"])
    c_msg = Message(
        conversation_id=graph["group"], sender_id=graph["c"], content="chain end",
        message_type=MessageType.TEXT, reply_to_id=b_msg.id,
    )
    db_session.add(c_msg)
    db_session.commit()

    db_session.execute(sa.text("delete from messages where id = :i"), {"i": graph["first"]})
    db_session.commit()
    db_session.expire_all()

    surviving = {m.content: m for m in db_session.scalars(sa.select(Message)).all()}
    assert "hi A" in surviving and "chain end" in surviving
    assert surviving["hi A"].reply_to_id is None, "pointer to the deleted root is cleared"
    assert surviving["chain end"].reply_to_id == b_msg.id, "the rest of the chain is intact"


# --- ownership cascade -----------------------------------------------------


def test_deleting_a_conversation_removes_everything_it_owns(
    db_session: Session, graph: dict
) -> None:
    """Conversation -> participants + messages -> statuses. Users and contacts stay."""
    db_session.execute(
        sa.text("delete from conversations where id = :i"), {"i": graph["group"]}
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(Conversation, graph["group"]) is None
    assert count(db_session, Message) == 0
    assert count(db_session, MessageStatus) == 0
    # Only the direct conversation's two participant rows remain.
    assert count(db_session, ConversationParticipant) == 2

    # Nothing a conversation does not own is touched.
    assert count(db_session, User) == 3
    assert count(db_session, Contact) == 2
    assert db_session.get(Conversation, graph["direct"]) is not None


def test_deleting_the_direct_conversation_leaves_the_group_untouched(
    db_session: Session, graph: dict
) -> None:
    db_session.execute(
        sa.text("delete from conversations where id = :i"), {"i": graph["direct"]}
    )
    db_session.commit()

    assert count(db_session, ConversationParticipant) == 3
    assert count(db_session, Message) == 3


# --- user deletion ---------------------------------------------------------


def test_deleting_a_user_with_history_is_refused_and_changes_nothing(
    db_session: Session, graph: dict
) -> None:
    """DOCUMENTED CURRENT BEHAVIOUR, not an aspiration.

    Three tables reference users with RESTRICT (conversation_participants,
    messages, message_status), so an account carrying history cannot be
    deleted at all. That is the deliberate default -- fail loudly rather than
    erase what someone said -- but it is not a complete account-deletion
    story. Tombstoning remains unresolved; see docs/model-conventions.md.
    """
    before = {
        m: count(db_session, m)
        for m in (User, Contact, Conversation, ConversationParticipant, Message, MessageStatus)
    }

    db_session.delete(db_session.get(User, graph["a"]))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    after = {
        m: count(db_session, m)
        for m in (User, Contact, Conversation, ConversationParticipant, Message, MessageStatus)
    }
    assert after == before, "a refused delete must leave the graph exactly as it was"


def test_the_refusal_comes_from_the_database_not_only_the_orm(
    db_session: Session, graph: dict
) -> None:
    """A raw DELETE bypasses SQLAlchemy entirely and must still be refused."""
    with pytest.raises(IntegrityError):
        db_session.execute(sa.text("delete from users where id = :i"), {"i": graph["a"]})
        db_session.commit()
    db_session.rollback()

    assert count(db_session, User) == 3
    assert count(db_session, Message) == 3


def test_a_user_with_no_history_can_still_be_deleted(db_session: Session) -> None:
    """RESTRICT only bites while references exist."""
    spare = User(username="spare", display_name="Spare", password_hash="hash")
    db_session.add(spare)
    db_session.commit()

    db_session.delete(spare)
    db_session.commit()

    assert db_session.scalars(sa.select(User).where(User.username == "spare")).first() is None


def test_contacts_alone_do_not_block_user_deletion(db_session: Session) -> None:
    """Contacts cascade, so they are not history in the way messages are."""
    x = User(username="x", display_name="X", password_hash="hash")
    y = User(username="y", display_name="Y", password_hash="hash")
    db_session.add_all([x, y])
    db_session.flush()
    db_session.add(Contact(user_id=x.id, contact_user_id=y.id))
    db_session.commit()

    db_session.delete(x)
    db_session.commit()

    assert count(db_session, Contact) == 0
    assert count(db_session, User) == 1


# --- invariants the database deliberately does not enforce -----------------


def test_the_database_does_not_enforce_direct_conversation_participant_count(
    db_session: Session, graph: dict
) -> None:
    """SERVICE-LAYER INVARIANT: a DIRECT conversation should have exactly two.

    Nothing stops a third participant being added at the database level.
    ConversationService owns this rule, and must also handle the race where
    two concurrent requests both find no existing direct conversation and each
    create one.
    """
    db_session.add(
        ConversationParticipant(conversation_id=graph["direct"], user_id=graph["c"])
    )
    db_session.commit()

    direct = db_session.get(Conversation, graph["direct"])
    assert len(direct.participants) == 3


def test_the_database_does_not_enforce_status_progression(
    db_session: Session, graph: dict
) -> None:
    """SERVICE-LAYER INVARIANT: READ should not fall back to SENT.

    MessageStatus stores state; it does not police transitions. Monotonic
    progression is service and WebSocket logic.
    """
    status = db_session.scalars(
        sa.select(MessageStatus).where(MessageStatus.message_id == graph["first"])
    ).first()
    assert status.status is DeliveryStatus.READ

    status.status = DeliveryStatus.SENT
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(MessageStatus, status.id).status is DeliveryStatus.SENT


def test_the_database_does_not_enforce_group_admin_rules(
    db_session: Session, graph: dict
) -> None:
    """SERVICE-LAYER INVARIANT: a group keeping at least one admin."""
    admin = db_session.scalars(
        sa.select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == graph["group"],
            ConversationParticipant.role == ParticipantRole.ADMIN,
        )
    ).one()
    admin.role = ParticipantRole.MEMBER
    db_session.commit()
    db_session.expire_all()

    group = db_session.get(Conversation, graph["group"])
    assert all(p.role is ParticipantRole.MEMBER for p in group.participants)
