"""The MessageStatus model: delivery and read state per message, per user."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import utcnow
from app.models.types import UtcDateTime, sa_enum

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class DeliveryStatus(enum.Enum):
    """How far a message has got for one recipient.

    Named DeliveryStatus rather than MessageStatus so the enum does not collide
    with the model class.
    """

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class MessageStatus(Base):
    """One recipient's delivery/read state for one message.

    There is at most one row per (message, user); the state moves forward in
    place rather than accumulating rows. Advancing it is service-layer work --
    nothing here enforces that READ cannot go back to SENT.
    """

    __tablename__ = "message_status"

    # A surrogate primary key with a unique constraint on the pair, rather than
    # the composite primary key used by Contact and ConversationParticipant.
    # Those rows are pure associations that nothing else references, so the
    # pair is their identity. A status row is a mutable entity with its own
    # lifecycle, and a single-column key keeps it addressable -- simpler for
    # ORM identity, and for anything that later needs to reference a status
    # row. The unique constraint still supplies the duplicate protection the
    # composite key would have given.
    id: Mapped[int] = mapped_column(primary_key=True)

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )

    # RESTRICT, matching Message.sender_id: deleting an account must not
    # silently rewrite who had read what.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    status: Mapped[DeliveryStatus] = mapped_column(
        sa_enum(DeliveryStatus, name="delivery_status"), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    message: Mapped["Message"] = relationship(back_populates="statuses")
    user: Mapped["User"] = relationship(back_populates="message_statuses")

    __table_args__ = (
        # Prevents duplicate rows for the same recipient, and its index has
        # message_id leading, which serves "who has read this message?".
        UniqueConstraint("message_id", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MessageStatus message_id={self.message_id} "
            f"user_id={self.user_id} status={self.status.value}>"
        )
