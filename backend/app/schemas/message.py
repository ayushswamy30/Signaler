"""Message schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import Message, MessageType
from app.models.message_status import DeliveryStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic

# How much of a quoted message the reply preview carries. The client shows one
# or two lines; sending the whole thing would duplicate long messages on every
# reply that quotes them.
REPLY_PREVIEW_LENGTH = 140


class ReplyPreview(BaseModel):
    """The quoted excerpt shown above a reply."""

    id: int
    sender_display_name: str
    content: str


class MessageRead(ORMModel):
    """A message as the client renders it.

    ``status`` is the sender's aggregate view of delivery and is computed, not
    stored on the row -- hence ``build`` rather than plain ``model_validate``.
    """

    id: int
    conversation_id: int
    sender: UserPublic
    content: str
    message_type: MessageType
    created_at: datetime
    edited_at: datetime | None = None
    status: DeliveryStatus | None = None
    reply_to: ReplyPreview | None = None

    @classmethod
    def build(cls, message: Message, status: DeliveryStatus | None = None) -> "MessageRead":
        """Assemble the response for one message."""
        reply = None
        if message.reply_to is not None:
            content = message.reply_to.content
            if len(content) > REPLY_PREVIEW_LENGTH:
                content = content[:REPLY_PREVIEW_LENGTH].rstrip() + "…"
            reply = ReplyPreview(
                id=message.reply_to.id,
                sender_display_name=message.reply_to.sender.display_name,
                content=content,
            )
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            sender=UserPublic.model_validate(message.sender),
            content=message.content,
            message_type=message.message_type,
            created_at=message.created_at,
            edited_at=message.edited_at,
            status=status,
            reply_to=reply,
        )


class MessageCreate(BaseModel):
    """A message being sent.

    Length is bounded here as well as in the service so an oversized body is
    rejected before it reaches the database layer; the service keeps its own
    check because it is also reachable from the WebSocket.
    """

    content: str = Field(min_length=1, max_length=4000)
    reply_to_id: int | None = None


class MessageUpdate(BaseModel):
    """New text for an existing message."""

    content: str = Field(min_length=1, max_length=4000)


class MarkReadRequest(BaseModel):
    """Advance the caller's read pointer.

    ``None`` means "everything currently in the conversation", which is what
    the client sends when a thread is simply opened and scrolled to the end.
    """

    up_to_message_id: int | None = None


class MessageList(BaseModel):
    """A page of history, oldest first.

    ``next_before_id`` is the cursor for the page before this one; ``None``
    means the caller has reached the start of the conversation.
    """

    messages: list[MessageRead]
    next_before_id: int | None = None
