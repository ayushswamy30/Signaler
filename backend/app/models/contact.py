"""The Contact model: one user's saved relationship with another user."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import utcnow
from app.models.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.user import User


class Contact(Base):
    """A directed link: ``user_id`` has saved ``contact_user_id`` as a contact.

    The link is one-way. A saving B says nothing about whether B has saved A;
    those are two independent rows.
    """

    __tablename__ = "contacts"

    # The pair is the identity of the row, so it is the primary key. That also
    # makes a duplicate (A -> B twice) a primary-key violation, with no separate
    # unique constraint needed.
    #
    # ondelete=CASCADE on BOTH sides: a contact row is meaningless once either
    # participant is gone, and enforcing it in the database means the rows
    # cannot survive a delete that bypasses the ORM.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    contact_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # A contact row records that a link was made; it is not edited afterwards,
    # so there is no updated_at. Same convention as TimestampMixin.created_at.
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)

    # Both foreign keys point at users.id, so SQLAlchemy cannot infer which one
    # each relationship travels; foreign_keys says so explicitly.
    owner: Mapped["User"] = relationship(
        back_populates="contacts", foreign_keys=[user_id]
    )
    contact_user: Mapped["User"] = relationship(
        back_populates="contact_of", foreign_keys=[contact_user_id]
    )

    def __repr__(self) -> str:
        return f"<Contact user_id={self.user_id} contact_user_id={self.contact_user_id}>"
