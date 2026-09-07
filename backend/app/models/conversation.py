"""The Conversation model: a direct or group conversation."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import TimestampMixin
from app.models.types import sa_enum

if TYPE_CHECKING:
    from app.models.conversation_participant import ConversationParticipant
    from app.models.message import Message


class ConversationType(enum.Enum):
    """Whether a conversation is one-to-one or a named group."""

    DIRECT = "direct"
    GROUP = "group"


class Conversation(TimestampMixin, Base):
    """A conversation, direct or group.

    One table serves both kinds, distinguished by ``type``. Splitting them into
    separate tables would duplicate the participant, message and read-state
    machinery for no gain, since everything below a conversation is identical
    either way.

    Shape rules -- that a direct conversation has exactly two participants, or
    that a group has a name -- are deliberately NOT enforced here. They are
    workflow rules belonging to the service layer; encoding them in the schema
    would make ordinary operations (creating a conversation before its
    participants exist, removing the last group member) impossible.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    type: Mapped[ConversationType] = mapped_column(
        sa_enum(ConversationType, name="conversation_type"), nullable=False
    )

    # Group conversations carry a name and avatar; direct ones are labelled by
    # the other participant, so both are nullable.
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Deleting a conversation deletes its participant rows: a participant row
    # describes membership of this conversation and means nothing without it.
    participants: Mapped[list["ConversationParticipant"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # A conversation owns its messages, so deleting it deletes them (and,
    # through Message, their status rows).
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} type={self.type.value}>"
