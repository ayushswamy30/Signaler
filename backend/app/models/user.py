"""The User model: a registered Signaler account."""

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.models.mixins import TimestampMixin
from app.models.types import UtcDateTime


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

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
