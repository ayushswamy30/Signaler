"""The User model: a registered Signaler account."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import TimestampMixin
from app.models.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.conversation_participant import ConversationParticipant


class User(TimestampMixin, Base):
    """A registered account.

    This is the parent entity for contacts, conversation participants and
    messages, which later stages add. It holds identity and presence only; it
    does no hashing, no validation and no presence bookkeeping of its own --
    those belong to the service layer.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The login identifier. Unique already creates a unique index, so an extra
    # index=True would only add a redundant second index on the same column.
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Optional: an account can exist without a phone number. UNIQUE treats NULLs
    # as distinct on both SQLite and PostgreSQL, so any number of users may have
    # none while a given number can still be claimed only once.
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Only ever a hash. Nothing here computes it, and a plaintext password must
    # never reach this column. Sized for any modern hash format.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Presence is written by the service and WebSocket layers, never by the
    # model: no onupdate hook, so an unrelated edit cannot silently mark a user
    # online or move their last-seen time.
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # Two separate relationships because contacts is directed and both of its
    # foreign keys point at this table: "people I saved" and "people who saved
    # me" are different sets and must not share a name.
    #
    # passive_deletes lets the database's ON DELETE CASCADE do the work. Without
    # it SQLAlchemy would load these rows on delete and try to NULL their
    # foreign keys, which is impossible here because they are primary-key
    # columns.
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="owner",
        foreign_keys="Contact.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    contact_of: Mapped[list["Contact"]] = relationship(
        back_populates="contact_user",
        foreign_keys="Contact.contact_user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Deliberately no delete cascade: the foreign key is RESTRICT, so deleting
    # a user who still participates in a conversation must fail rather than
    # quietly removing them from it. A cascade here would delete the rows the
    # database is trying to protect. passive_deletes stops SQLAlchemy loading
    # them to NULL a primary-key column, letting the RESTRICT surface instead.
    #
    # No User.conversations shortcut: the association object carries role,
    # joined_at and read state, so hiding it behind a many-to-many would only
    # obscure the thing callers actually need.
    conversation_participations: Mapped[list["ConversationParticipant"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
