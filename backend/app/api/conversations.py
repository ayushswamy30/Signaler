"""Conversation routes, including the message history of a conversation."""

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.message_status import DeliveryStatus
from app.schemas.common import Message as MessageResponse
from app.schemas.conversation import (
    ConversationRead,
    DirectConversationCreate,
    MuteUpdate,
    ParticipantRead,
)
from app.schemas.message import MarkReadRequest, MessageCreate, MessageList, MessageRead
from app.services import conversation_service, group_service, message_service
from app.websocket import broadcast

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _render(db: Session, summary: conversation_service.ConversationSummary) -> ConversationRead:
    """Attach the last message, with its delivery state, to a summary."""
    last = summary.last_message
    return ConversationRead.build(
        summary,
        MessageRead.build(last, message_service.aggregate_status(db, last)) if last else None,
    )


@router.get("", response_model=list[ConversationRead])
def list_conversations(db: DbSession, current_user: CurrentUser) -> list[ConversationRead]:
    """Every conversation the caller is in, most recent activity first."""
    summaries = conversation_service.list_for_user(db, current_user.id)
    # One query for the delivery state of every last message, rather than one
    # per row: the list is the first thing the client loads.
    statuses = message_service.aggregate_statuses(
        db, [s.last_message for s in summaries if s.last_message]
    )
    return [
        ConversationRead.build(
            summary,
            MessageRead.build(summary.last_message, statuses.get(summary.last_message.id))
            if summary.last_message
            else None,
        )
        for summary in summaries
    ]


@router.post("/direct", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def open_direct_conversation(
    payload: DirectConversationCreate, db: DbSession, current_user: CurrentUser
) -> ConversationRead:
    """Open the one-to-one conversation with another user, creating it if new.

    Always 201, even when the conversation already existed: the client's
    concern is "give me the thread with this person", and reporting the two
    cases differently would only give it a branch with no different behaviour.
    """
    existing = conversation_service.find_direct_conversation(
        db, user_id=current_user.id, other_user_id=payload.user_id
    )
    conversation = conversation_service.get_or_create_direct(
        db, user_id=current_user.id, other_user_id=payload.user_id
    )
    if existing is None:
        broadcast.conversation_created(db, conversation)

    summary = conversation_service.get_summary_for_user(
        db, conversation_id=conversation.id, user_id=current_user.id
    )
    return _render(db, summary)


@router.get("/{conversation_id}", response_model=ConversationRead)
def read_conversation(
    conversation_id: int, db: DbSession, current_user: CurrentUser
) -> ConversationRead:
    """One conversation, as the caller sees it."""
    summary = conversation_service.get_summary_for_user(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    return _render(db, summary)


@router.get("/{conversation_id}/members", response_model=list[ParticipantRead])
def list_members(
    conversation_id: int, db: DbSession, current_user: CurrentUser
) -> list[ParticipantRead]:
    """The membership of a conversation. Admins first, then join order."""
    members = group_service.list_members(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    return [ParticipantRead.model_validate(member) for member in members]


@router.get("/{conversation_id}/messages", response_model=MessageList)
def list_messages(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=settings.max_page_size),
    before_id: int | None = Query(
        default=None, description="Return messages older than this id (pagination cursor)"
    ),
) -> MessageList:
    """A page of history, oldest first.

    ``next_before_id`` is the cursor for the previous page. It is only set when
    the page came back full: a short page means the conversation has no more
    history, and returning a cursor there would cost the client a wasted round
    trip to discover that.
    """
    messages = message_service.list_history(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        limit=limit,
        before_id=before_id,
    )
    statuses = message_service.aggregate_statuses(db, messages)
    return MessageList(
        messages=[MessageRead.build(m, statuses.get(m.id)) for m in messages],
        next_before_id=messages[0].id if len(messages) == limit else None,
    )


@router.post(
    "/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED
)
def send_message(
    conversation_id: int, payload: MessageCreate, db: DbSession, current_user: CurrentUser
) -> MessageRead:
    """Send a message. The socket delivers it to everyone, sender included."""
    message = message_service.send_message(
        db,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=payload.content,
        reply_to_id=payload.reply_to_id,
    )
    broadcast.message_created(db, message)
    return MessageRead.build(message, message_service.aggregate_status(db, message))


@router.post("/{conversation_id}/read", response_model=MessageResponse)
def mark_read(
    conversation_id: int,
    payload: MarkReadRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """Mark a conversation read up to a message, or to the end by default."""
    changed = message_service.mark_read(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        up_to_message_id=payload.up_to_message_id,
    )
    broadcast.message_status_changed(db, message_ids=changed, status=DeliveryStatus.READ)
    return MessageResponse(detail=f"Marked {len(changed)} messages as read.")


@router.patch("/{conversation_id}/mute", response_model=ConversationRead)
def set_mute(
    conversation_id: int, payload: MuteUpdate, db: DbSession, current_user: CurrentUser
) -> ConversationRead:
    """Mute or unmute a conversation for the caller only."""
    conversation_service.set_muted(
        db, conversation_id=conversation_id, user_id=current_user.id, muted=payload.muted
    )
    summary = conversation_service.get_summary_for_user(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    return _render(db, summary)
