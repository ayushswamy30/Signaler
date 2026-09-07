"""Messages: sending, history, edits, deletion, and delivery state."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.models.conversation_participant import ConversationParticipant
from app.models.message import Message, MessageType
from app.models.message_status import DeliveryStatus, MessageStatus
from app.models.mixins import utcnow
from app.services import conversation_service

MAX_CONTENT_LENGTH = 4000

# Ranked so an aggregate can be computed by taking the *lowest* state any
# recipient is in: a message is only "read" once nobody is behind that.
_STATUS_ORDER = {DeliveryStatus.SENT: 0, DeliveryStatus.DELIVERED: 1, DeliveryStatus.READ: 2}


def _clean_content(content: str) -> str:
    """Validate and normalise message text.

    Whitespace-only content is rejected rather than stored: an empty bubble is
    never something a user meant to send.
    """
    content = content.strip()
    if not content:
        raise ValidationError("A message cannot be empty.")
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValidationError(f"A message cannot exceed {MAX_CONTENT_LENGTH} characters.")
    return content


def get_message(db: Session, message_id: int) -> Message:
    """Return a message by id, or raise NotFoundError."""
    message = db.get(Message, message_id)
    if message is None:
        raise NotFoundError(f"No message with id {message_id}.")
    return message


def send_message(
    db: Session,
    *,
    conversation_id: int,
    sender_id: int,
    content: str,
    reply_to_id: int | None = None,
) -> Message:
    """Post a message into a conversation the sender belongs to.

    One SENT status row is created per *other* participant. The sender gets no
    row: their own copy is trivially delivered and read, and a self-row would
    have to be excluded from every aggregate afterwards.
    """
    conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=sender_id
    )
    content = _clean_content(content)

    if reply_to_id is not None:
        target = db.get(Message, reply_to_id)
        # A reply must point inside the same conversation, or quoting it would
        # leak text from a conversation the reader may not be in.
        if target is None or target.conversation_id != conversation_id:
            raise NotFoundError("The message being replied to is not in this conversation.")

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        message_type=MessageType.TEXT,
        reply_to_id=reply_to_id,
    )
    db.add(message)
    db.flush()

    recipients = [
        user_id
        for user_id in conversation_service.participant_ids(db, conversation_id)
        if user_id != sender_id
    ]
    db.add_all(
        MessageStatus(message_id=message.id, user_id=user_id, status=DeliveryStatus.SENT)
        for user_id in recipients
    )

    # Bumps updated_at, which is what orders a conversation list that has no
    # messages yet against one that just received its first.
    message.conversation.updated_at = utcnow()

    db.commit()
    db.refresh(message)
    return message


def list_history(
    db: Session,
    *,
    conversation_id: int,
    user_id: int,
    limit: int = 50,
    before_id: int | None = None,
) -> list[Message]:
    """A page of conversation history, oldest first.

    Paged by message id rather than by offset: a chat gains rows at the end
    constantly, and an offset page would skip or repeat messages as it shifts.
    The query walks backwards from ``before_id`` and the page is reversed, so
    the caller always receives messages in reading order.
    """
    conversation_service.require_participant(db, conversation_id=conversation_id, user_id=user_id)
    limit = max(1, min(limit, settings.max_page_size))

    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .options(selectinload(Message.sender), selectinload(Message.reply_to))
        .order_by(Message.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        statement = statement.where(Message.id < before_id)

    return list(reversed(list(db.scalars(statement))))


def edit_message(db: Session, *, message_id: int, user_id: int, content: str) -> Message:
    """Change the text of a message. Only its sender may do this."""
    message = get_message(db, message_id)
    conversation_service.require_participant(
        db, conversation_id=message.conversation_id, user_id=user_id
    )
    if message.sender_id != user_id:
        raise PermissionDeniedError("You can only edit your own messages.")

    message.content = _clean_content(content)
    message.edited_at = utcnow()
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, *, message_id: int, user_id: int) -> int:
    """Delete a message, returning the conversation id it belonged to.

    The sender may delete their own message; a group admin may delete anyone's,
    which is the only moderation tool the group has. Replies to a deleted
    message survive with their quote pointer cleared -- see Message.reply_to_id.
    """
    message = get_message(db, message_id)
    participant = conversation_service.require_participant(
        db, conversation_id=message.conversation_id, user_id=user_id
    )
    from app.models.conversation_participant import ParticipantRole

    if message.sender_id != user_id and participant.role is not ParticipantRole.ADMIN:
        raise PermissionDeniedError("You can only delete your own messages.")

    conversation_id = message.conversation_id
    # Read pointers referencing this message are cleared by the foreign key's
    # ON DELETE SET NULL, so no bookkeeping is needed here.
    db.delete(message)
    db.commit()
    return conversation_id


def mark_delivered(db: Session, *, user_id: int, conversation_id: int | None = None) -> list[int]:
    """Move this user's pending statuses to DELIVERED.

    Called when a client connects: everything sent while they were away is now
    on their device. Returns the message ids that actually changed, so the
    realtime layer only notifies senders whose state really moved.
    """
    statement = (
        select(MessageStatus)
        .join(Message, MessageStatus.message_id == Message.id)
        .where(MessageStatus.user_id == user_id, MessageStatus.status == DeliveryStatus.SENT)
    )
    if conversation_id is not None:
        statement = statement.where(Message.conversation_id == conversation_id)

    pending = list(db.scalars(statement))
    for status in pending:
        status.status = DeliveryStatus.DELIVERED
    if pending:
        db.commit()
    return [status.message_id for status in pending]


def mark_read(
    db: Session, *, conversation_id: int, user_id: int, up_to_message_id: int | None = None
) -> list[int]:
    """Mark a conversation read for one user and advance their read pointer.

    Returns the message ids whose status changed. A bulk UPDATE keyed on the
    message ids does the status change: a conversation can be marked read after
    hundreds of unread messages, and loading them all to set one column each
    would be wasteful.
    """
    participant = conversation_service.mark_read(
        db, conversation_id=conversation_id, user_id=user_id, up_to_message_id=up_to_message_id
    )
    ceiling = participant.last_read_message_id
    if ceiling is None:
        return []

    unread_ids = list(
        db.scalars(
            select(MessageStatus.message_id)
            .join(Message, MessageStatus.message_id == Message.id)
            .where(
                MessageStatus.user_id == user_id,
                MessageStatus.status != DeliveryStatus.READ,
                Message.conversation_id == conversation_id,
                Message.id <= ceiling,
            )
        )
    )
    if not unread_ids:
        return []

    db.execute(
        update(MessageStatus)
        .where(MessageStatus.user_id == user_id, MessageStatus.message_id.in_(unread_ids))
        .values(status=DeliveryStatus.READ, updated_at=utcnow())
    )
    db.commit()
    return unread_ids


def aggregate_status(db: Session, message: Message) -> DeliveryStatus | None:
    """How far a message has got overall, from its sender's point of view.

    The lowest state any recipient is in: one unread recipient keeps the whole
    message at "delivered". Returns None when there are no recipient rows,
    which is what a message in a conversation of one looks like.
    """
    statuses = list(
        db.scalars(select(MessageStatus.status).where(MessageStatus.message_id == message.id))
    )
    if not statuses:
        return None
    return min(statuses, key=lambda status: _STATUS_ORDER[status])


def aggregate_statuses(db: Session, messages: list[Message]) -> dict[int, DeliveryStatus]:
    """``aggregate_status`` for a page of messages, in one query.

    The minimum of an ordered enum is not something SQL can take directly, so
    the rank is applied in Python over one flat result set -- still a single
    round trip, unlike calling aggregate_status per message.
    """
    message_ids = [message.id for message in messages]
    if not message_ids:
        return {}

    lowest: dict[int, DeliveryStatus] = {}
    rows = db.execute(
        select(MessageStatus.message_id, MessageStatus.status).where(
            MessageStatus.message_id.in_(message_ids)
        )
    ).all()
    for message_id, status in rows:
        current = lowest.get(message_id)
        if current is None or _STATUS_ORDER[status] < _STATUS_ORDER[current]:
            lowest[message_id] = status
    return lowest


def unread_total(db: Session, user_id: int) -> int:
    """Total unread messages across every conversation, for the app badge."""
    return (
        db.scalar(
            select(func.count(Message.id))
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Message.conversation_id,
            )
            .where(
                ConversationParticipant.user_id == user_id,
                Message.sender_id != user_id,
                Message.id > func.coalesce(ConversationParticipant.last_read_message_id, 0),
            )
        )
        or 0
    )
