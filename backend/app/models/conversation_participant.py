"""The ConversationParticipant model: one user's membership of a conversation."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import utcnow
from app.models.types import UtcDateTime, sa_enum

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class ParticipantRole(enum.Enum):
    """A participant's role within a conversation.

    Structural only. What an ADMIN may actually do is authorisation logic for
    the service layer; nothing here enforces that a group has an admin, or has
    only one.
    """

    MEMBER = "member"
    ADMIN = "admin"


class ConversationParticipant(Base):
    """A user's membership of a conversation.

    This is an association object rather than a plain many-to-many table
    because the membership carries its own state: a role, when the user
    joined, and how far they have read.
    """

    __tablename__ = "conversation_participants"

    # The pair is the identity of the membership, so it is the primary key --
    # a user cannot join the same conversation twice. Same pattern as Contact.
    #
    # CASCADE from conversations: membership cannot outlive its conversation.
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )

    # RESTRICT from users, deliberately NOT cascade. Deleting an account must
    # not silently erase its membership of group conversations, which is part
    # of the conversation's history. The database refuses instead, so account
    # deletion has to be designed (tombstone or soft delete) rather than
    # defaulting to destruction. See docs/model-conventions.md.
    #
    # The index supports "every conversation this user is in", the query behind
    # the conversation list. The composite primary key already covers lookups
    # that start with conversation_id, but not ones that start with user_id.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True
    )

    role: Mapped[ParticipantRole] = mapped_column(
        sa_enum(ParticipantRole, name="participant_role"),
        default=ParticipantRole.MEMBER,
        nullable=False,
    )

    joined_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)

    # Read state. Intentionally a bare integer with no foreign key: the
    # messages table does not exist yet, and inventing a placeholder Message
    # model to satisfy it would be worse than waiting. A migration adds the
    # foreign key to messages.id when that model lands.
    last_read_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="conversation_participations")

    def __repr__(self) -> str:
        return (
            f"<ConversationParticipant conversation_id={self.conversation_id} "
            f"user_id={self.user_id} role={self.role.value}>"
        )
