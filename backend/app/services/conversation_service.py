"""Conversations: membership, the conversation list, and read state.

Group-specific operations (creating a group, managing members) live in
``group_service``; everything here applies to direct and group conversations
alike.
"""

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant, ParticipantRole
from app.models.message import Message
from app.services import user_service


@dataclass(frozen=True)
class ConversationSummary:
    """A conversation as the conversation list needs it.

    The list needs three things the ``Conversation`` row does not carry -- the
    last message, the viewer's unread count, and the viewer's own membership --
    and computing them per row in the route would mean N+1 queries.
    """

    conversation: Conversation
    participant: ConversationParticipant
    last_message: Message | None
    unread_count: int

    @property
    def last_activity(self):
        """When the conversation last changed, for ordering the list."""
        return self.last_message.created_at if self.last_message else self.conversation.created_at


def get_conversation(db: Session, conversation_id: int) -> Conversation:
    """Return a conversation by id, or raise NotFoundError."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise NotFoundError(f"No conversation with id {conversation_id}.")
    return conversation


def get_participant(
    db: Session, *, conversation_id: int, user_id: int
) -> ConversationParticipant | None:
    """Return a membership row, or None if the user is not in the conversation."""
    return db.get(ConversationParticipant, (conversation_id, user_id))


def require_participant(
    db: Session, *, conversation_id: int, user_id: int
) -> ConversationParticipant:
    """The authorisation gate every conversation-scoped operation goes through.

    A conversation the caller is not in is reported as *not found*, not as
    *forbidden*: telling an outsider that conversation 42 exists but is closed
    to them leaks the shape of other people's conversations.
    """
    participant = get_participant(db, conversation_id=conversation_id, user_id=user_id)
    if participant is None:
        raise NotFoundError(f"No conversation with id {conversation_id}.")
    return participant


def require_admin(db: Session, *, conversation_id: int, user_id: int) -> ConversationParticipant:
    """Like require_participant, but the caller must also be an admin."""
    participant = require_participant(db, conversation_id=conversation_id, user_id=user_id)
    if participant.role is not ParticipantRole.ADMIN:
        raise PermissionDeniedError("Only a group admin can do that.")
    return participant


def participant_ids(db: Session, conversation_id: int) -> list[int]:
    """The user ids in a conversation -- the audience for a realtime event."""
    return list(
        db.scalars(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
    )


def related_user_ids(db: Session, user_id: int) -> set[int]:
    """Everyone who shares at least one conversation with this user.

    The audience for a presence change: those are exactly the people whose
    screens show this user, and broadcasting more widely would tell strangers
    when someone is at their desk.
    """
    mine = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == user_id
    )
    others = db.scalars(
        select(ConversationParticipant.user_id)
        .where(
            ConversationParticipant.conversation_id.in_(mine),
            ConversationParticipant.user_id != user_id,
        )
        .distinct()
    )
    return set(others)


def find_direct_conversation(db: Session, *, user_id: int, other_user_id: int) -> Conversation | None:
    """The existing one-to-one conversation between two users, if there is one.

    "Exactly these two people" is the condition, so a two-person *group* is not
    mistaken for a direct conversation: the subquery counts the conversation's
    total membership as well as the matches.
    """
    memberships = (
        select(ConversationParticipant.conversation_id)
        .where(ConversationParticipant.user_id.in_((user_id, other_user_id)))
        .group_by(ConversationParticipant.conversation_id)
        .having(func.count(ConversationParticipant.user_id) == 2)
    )
    total = (
        select(ConversationParticipant.conversation_id)
        .group_by(ConversationParticipant.conversation_id)
        .having(func.count(ConversationParticipant.user_id) == 2)
    )
    statement = select(Conversation).where(
        Conversation.type == ConversationType.DIRECT,
        Conversation.id.in_(memberships),
        Conversation.id.in_(total),
    )
    return db.scalars(statement).first()


def get_or_create_direct(db: Session, *, user_id: int, other_user_id: int) -> Conversation:
    """Open the conversation with another user, creating it on first contact.

    Idempotent by design: the UI calls this whenever someone taps a name, and a
    second tap must land in the same thread rather than forking a new one.
    """
    if user_id == other_user_id:
        raise ValidationError("You cannot start a conversation with yourself.")
    user_service.get_user(db, other_user_id)

    existing = find_direct_conversation(db, user_id=user_id, other_user_id=other_user_id)
    if existing is not None:
        return existing

    conversation = Conversation(type=ConversationType.DIRECT)
    conversation.participants = [
        ConversationParticipant(user_id=user_id),
        ConversationParticipant(user_id=other_user_id),
    ]
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _unread_count_subquery() -> Select:
    """Per-conversation unread counts for one viewer.

    A message counts as unread when it is newer than the viewer's read pointer
    and someone else sent it. Ordering by id rather than timestamp is
    deliberate: ids are assigned in insert order and are unique, so two
    messages in the same microsecond still compare consistently.
    """
    return (
        select(
            Message.conversation_id.label("conversation_id"),
            func.count(Message.id).label("unread"),
        )
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Message.conversation_id,
        )
        .where(
            Message.sender_id != ConversationParticipant.user_id,
            Message.id > func.coalesce(ConversationParticipant.last_read_message_id, 0),
        )
        .group_by(Message.conversation_id, ConversationParticipant.user_id)
    )


def list_for_user(db: Session, user_id: int) -> list[ConversationSummary]:
    """Every conversation a user belongs to, most recent activity first.

    Assembled in three queries regardless of list length -- memberships, last
    messages, unread counts -- rather than a per-conversation round trip.
    """
    memberships = list(
        db.scalars(
            select(ConversationParticipant)
            .where(ConversationParticipant.user_id == user_id)
            .options(
                selectinload(ConversationParticipant.conversation)
                .selectinload(Conversation.participants)
                .selectinload(ConversationParticipant.user)
            )
        )
    )
    if not memberships:
        return []

    conversation_ids = [m.conversation_id for m in memberships]

    # The newest message per conversation. Max(id) rather than max(created_at):
    # same reasoning as the unread count, and it reuses the primary key.
    newest_ids = select(func.max(Message.id)).where(
        Message.conversation_id.in_(conversation_ids)
    ).group_by(Message.conversation_id)
    last_messages = {
        message.conversation_id: message
        for message in db.scalars(
            select(Message).where(Message.id.in_(newest_ids)).options(selectinload(Message.sender))
        )
    }

    unread = dict(
        db.execute(
            _unread_count_subquery().where(
                ConversationParticipant.user_id == user_id,
                Message.conversation_id.in_(conversation_ids),
            )
        ).all()
    )

    summaries = [
        ConversationSummary(
            conversation=membership.conversation,
            participant=membership,
            last_message=last_messages.get(membership.conversation_id),
            unread_count=unread.get(membership.conversation_id, 0),
        )
        for membership in memberships
    ]
    summaries.sort(key=lambda s: s.last_activity, reverse=True)
    return summaries


def get_summary_for_user(db: Session, *, conversation_id: int, user_id: int) -> ConversationSummary:
    """One conversation, in the same shape the list uses.

    Used after creating or opening a conversation so the client can insert the
    row without refetching the whole list.
    """
    participant = require_participant(db, conversation_id=conversation_id, user_id=user_id)
    last_message = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(1)
    ).first()
    unread = db.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.id > (participant.last_read_message_id or 0),
        )
    )
    return ConversationSummary(
        conversation=participant.conversation,
        participant=participant,
        last_message=last_message,
        unread_count=unread or 0,
    )


def mark_read(
    db: Session, *, conversation_id: int, user_id: int, up_to_message_id: int | None = None
) -> ConversationParticipant:
    """Advance the caller's read pointer, by default to the newest message.

    The pointer only ever moves forward. An out-of-order acknowledgement from a
    client whose messages arrived late must not reopen messages the user has
    already seen.
    """
    participant = require_participant(db, conversation_id=conversation_id, user_id=user_id)

    if up_to_message_id is None:
        up_to_message_id = db.scalar(
            select(func.max(Message.id)).where(Message.conversation_id == conversation_id)
        )
        if up_to_message_id is None:
            return participant
    else:
        message = db.get(Message, up_to_message_id)
        if message is None or message.conversation_id != conversation_id:
            raise NotFoundError("That message is not in this conversation.")

    if up_to_message_id > (participant.last_read_message_id or 0):
        participant.last_read_message_id = up_to_message_id
        db.commit()
        db.refresh(participant)
    return participant


def set_muted(db: Session, *, conversation_id: int, user_id: int, muted: bool) -> ConversationParticipant:
    """Mute or unmute a conversation for one member only."""
    participant = require_participant(db, conversation_id=conversation_id, user_id=user_id)
    participant.muted = muted
    db.commit()
    db.refresh(participant)
    return participant


def add_participant(
    db: Session,
    *,
    conversation_id: int,
    user_id: int,
    role: ParticipantRole = ParticipantRole.MEMBER,
    commit: bool = True,
) -> ConversationParticipant:
    """Put a user into a conversation.

    Shared by group creation and by adding a member later, which is why it
    takes ``commit`` -- group creation adds several people in one transaction.
    """
    user_service.get_user(db, user_id)
    if get_participant(db, conversation_id=conversation_id, user_id=user_id) is not None:
        raise ConflictError("That user is already in this conversation.")

    participant = ConversationParticipant(
        conversation_id=conversation_id, user_id=user_id, role=role
    )
    db.add(participant)
    if commit:
        db.commit()
        db.refresh(participant)
    else:
        db.flush()
    return participant
