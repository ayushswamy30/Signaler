"""The Message model: one persisted message in a conversation."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import utcnow
from app.models.types import UtcDateTime, sa_enum

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_status import MessageStatus
    from app.models.user import User


class MessageType(enum.Enum):
    """What kind of payload a message carries.

    Only TEXT exists today. The column is a fixed-width VARCHAR holding the
    member value, so attachment and system types can be added later without a
    schema change -- see sa_enum in app/models/types.py.
    """

    TEXT = "text"


class Message(Base):
    """A message sent by a user into a conversation.

    The model stores content and metadata only. It performs no validation
    (rejecting empty content belongs to the schema/service layer), no edit
    bookkeeping, and no expiry behaviour -- ``edited_at`` and ``expires_at``
    are recorded by services when those features are built.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    # A conversation owns its messages: deleting it removes them.
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )

    # RESTRICT, never CASCADE. Deleting an account must not erase what that
    # person said in other people's conversations. Consistent with
    # ConversationParticipant.user_id; see docs/model-conventions.md, where
    # account deletion is recorded as an unresolved decision.
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    message_type: Mapped[MessageType] = mapped_column(
        sa_enum(MessageType, name="message_type"), nullable=False
    )

    # SET NULL, not RESTRICT. A reply is history and must outlive the message
    # it answers; the pointer is simply cleared. RESTRICT would additionally
    # make a conversation containing any reply impossible to delete, because
    # the cascade would hit messages referencing each other.
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)

    # Set by a service when a message is edited or given an expiry. No model
    # level automation: an unrelated write must not mark a message edited.
    edited_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(back_populates="sent_messages")

    # Self-referential: remote_side marks which end is the "one" side, and
    # foreign_keys names the column both directions travel.
    reply_to: Mapped["Message | None"] = relationship(
        back_populates="replies", remote_side=[id], foreign_keys=[reply_to_id]
    )
    replies: Mapped[list["Message"]] = relationship(
        back_populates="reply_to",
        foreign_keys=[reply_to_id],
        # No delete cascade: replies survive their target. passive_deletes lets
        # the database's SET NULL clear the pointer.
        passive_deletes=True,
    )

    statuses: Mapped[list["MessageStatus"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # The conversation history query is
        #   WHERE conversation_id = ? ORDER BY created_at
        # so one composite index serves both the filter and the ordering. A
        # plain conversation_id index would still leave a sort; two separate
        # indexes would not combine as well and cost more on write.
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id}>"
