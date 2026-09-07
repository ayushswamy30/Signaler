"""Domain events, published to the people entitled to see them.

Every function here answers two questions in one place: what an event looks
like on the wire, and who its audience is. Routes call these instead of
assembling payloads themselves, so an event has one shape whether it originated
over HTTP or over a socket.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_participant import ConversationParticipant, ParticipantRole
from app.models.message import Message
from app.models.message_status import DeliveryStatus
from app.models.user import User
from app.schemas.conversation import ConversationRead, ParticipantRead
from app.schemas.message import MessageRead
from app.schemas.user import UserPublic
from app.services import conversation_service, message_service
from app.websocket import events


def _json(model: Any) -> Any:
    """Serialise a schema the way the HTTP layer would.

    ``mode="json"`` matters: datetimes and enums must arrive as strings, not as
    Python objects the JSON encoder would refuse.
    """
    return model.model_dump(mode="json")


def message_created(db: Session, message: Message) -> None:
    """A new message, to everyone in the conversation including the sender.

    The sender receives it too, so their *other* devices show what they sent
    from this one and every copy carries the same server-assigned id.
    """
    payload = events.event(
        events.MESSAGE_NEW,
        message=_json(MessageRead.build(message, message_service.aggregate_status(db, message))),
    )
    events.publish(conversation_service.participant_ids(db, message.conversation_id), payload)


def message_updated(db: Session, message: Message) -> None:
    """An edited message, carrying its new text."""
    payload = events.event(
        events.MESSAGE_UPDATED,
        message=_json(MessageRead.build(message, message_service.aggregate_status(db, message))),
    )
    events.publish(conversation_service.participant_ids(db, message.conversation_id), payload)


def message_deleted(db: Session, *, conversation_id: int, message_id: int) -> None:
    """A deleted message, by id -- the row itself is already gone."""
    events.publish(
        conversation_service.participant_ids(db, conversation_id),
        events.event(
            events.MESSAGE_DELETED, conversation_id=conversation_id, message_id=message_id
        ),
    )


def message_status_changed(db: Session, *, message_ids: list[int], status: DeliveryStatus) -> None:
    """Delivery ticks, sent only to the senders of the affected messages.

    Nobody else has a use for them: a recipient does not display whether a
    third party has read something. Senders are looked up in one query and the
    ids grouped per sender, so a read receipt covering 200 messages is one
    event per sender rather than 200 events.
    """
    if not message_ids:
        return

    by_sender: dict[int, list[int]] = defaultdict(list)
    rows = db.execute(
        select(Message.id, Message.sender_id, Message.conversation_id).where(
            Message.id.in_(message_ids)
        )
    ).all()
    conversation_ids: dict[int, int] = {}
    for message_id, sender_id, conversation_id in rows:
        by_sender[sender_id].append(message_id)
        conversation_ids[sender_id] = conversation_id

    for sender_id, ids in by_sender.items():
        events.publish(
            [sender_id],
            events.event(
                events.MESSAGE_STATUS,
                conversation_id=conversation_ids[sender_id],
                message_ids=sorted(ids),
                status=status.value,
            ),
        )


def typing(db: Session, *, conversation_id: int, user: User, is_typing: bool) -> None:
    """A typing indicator, to the other people in the conversation.

    Never echoed to the typist: a client that showed you typing to yourself
    would be showing you your own keystrokes twice.
    """
    audience = [
        user_id
        for user_id in conversation_service.participant_ids(db, conversation_id)
        if user_id != user.id
    ]
    events.publish(
        audience,
        events.event(
            events.TYPING_START if is_typing else events.TYPING_STOP,
            conversation_id=conversation_id,
            user=_json(UserPublic.model_validate(user)),
        ),
    )


def presence(db: Session, user: User) -> None:
    """An online/offline change, to everyone who shares a conversation."""
    events.publish(
        conversation_service.related_user_ids(db, user.id),
        events.event(
            events.PRESENCE,
            user_id=user.id,
            is_online=user.is_online,
            last_seen=user.last_seen.isoformat() if user.last_seen else None,
        ),
    )


def _conversation_for(db: Session, conversation: Conversation, viewer_id: int) -> dict[str, Any]:
    """Render a conversation as one viewer sees it."""
    summary = conversation_service.get_summary_for_user(
        db, conversation_id=conversation.id, user_id=viewer_id
    )
    last = summary.last_message
    return _json(
        ConversationRead.build(
            summary,
            MessageRead.build(last, message_service.aggregate_status(db, last)) if last else None,
        )
    )


def conversation_created(db: Session, conversation: Conversation) -> None:
    """A conversation appearing for the first time.

    Sent one recipient at a time, because the payload is viewer-relative: the
    unread count, mute flag and role differ per member.
    """
    for user_id in conversation_service.participant_ids(db, conversation.id):
        events.publish(
            [user_id],
            events.event(
                events.CONVERSATION_CREATED,
                conversation=_conversation_for(db, conversation, user_id),
            ),
        )


def conversation_updated(db: Session, conversation: Conversation) -> None:
    """A renamed group, a new avatar, or a membership change."""
    for user_id in conversation_service.participant_ids(db, conversation.id):
        events.publish(
            [user_id],
            events.event(
                events.CONVERSATION_UPDATED,
                conversation=_conversation_for(db, conversation, user_id),
            ),
        )


def conversation_removed(*, user_ids: list[int], conversation_id: int) -> None:
    """A conversation that is gone for these users -- deleted, left, or removed from.

    Takes explicit ids rather than looking them up: by the time this is sent the
    membership row is already deleted, so there is nothing left to query.
    """
    events.publish(
        user_ids,
        events.event(events.CONVERSATION_DELETED, conversation_id=conversation_id),
    )


def members_added(
    db: Session, conversation: Conversation, added: list[ConversationParticipant]
) -> None:
    """New members in a group.

    The two audiences need different events: a newcomer has never seen this
    conversation and gets the whole thing, while an existing member already has
    it on screen and only needs the delta.
    """
    added_ids = {participant.user_id for participant in added}
    existing_ids = [
        user_id
        for user_id in conversation_service.participant_ids(db, conversation.id)
        if user_id not in added_ids
    ]

    for user_id in added_ids:
        events.publish(
            [user_id],
            events.event(
                events.CONVERSATION_CREATED,
                conversation=_conversation_for(db, conversation, user_id),
            ),
        )
    events.publish(
        existing_ids,
        events.event(
            events.GROUP_MEMBERS_ADDED,
            conversation_id=conversation.id,
            members=[_json(ParticipantRead.model_validate(p)) for p in added],
        ),
    )


def member_removed(db: Session, *, conversation_id: int, member_id: int) -> None:
    """Someone left or was removed. The group hears about it; so does the leaver."""
    events.publish(
        conversation_service.participant_ids(db, conversation_id),
        events.event(
            events.GROUP_MEMBER_REMOVED, conversation_id=conversation_id, user_id=member_id
        ),
    )
    conversation_removed(user_ids=[member_id], conversation_id=conversation_id)


def role_changed(
    db: Session, *, conversation_id: int, member_id: int, role: ParticipantRole
) -> None:
    """A promotion or demotion within a group."""
    events.publish(
        conversation_service.participant_ids(db, conversation_id),
        events.event(
            events.GROUP_ROLE_CHANGED,
            conversation_id=conversation_id,
            user_id=member_id,
            role=role.value,
        ),
    )
