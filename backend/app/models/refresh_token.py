"""The RefreshToken model: one long-lived session belonging to a user."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.mixins import utcnow
from app.models.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    """A refresh token issued at login and rotated on every use.

    The row stores a SHA-256 hash, never the token itself, so a database leak
    does not hand out live sessions. Rotation means each token is single-use:
    refreshing revokes the presented token and issues a new one, which makes a
    stolen-and-replayed token detectable (it will already be revoked).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)

    # CASCADE, unlike the other user foreign keys: a session is not history
    # worth preserving, and an account that goes away should take its live
    # sessions with it rather than blocking on them.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Unique: two sessions cannot collide, and the index is what the refresh
    # lookup uses -- tokens are found by hash, never by id.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)

    # Set instead of deleting the row, so a replayed token is distinguishable
    # from one that never existed. A cleanup job can prune old rows later.
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # Free-form client description, for a future "active sessions" screen.
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        """True while the token may still be exchanged."""
        return self.revoked_at is None and self.expires_at > utcnow()

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"
