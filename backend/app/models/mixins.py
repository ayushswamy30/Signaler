"""Reusable model mixins."""

from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import UtcDateTime


def utcnow() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` to a model.

    The values are generated in Python rather than by the database. SQLite's
    CURRENT_TIMESTAMP has whole-second resolution, which is too coarse to order
    messages that arrive in the same second, and it is not driven by the ORM's
    onupdate hook. Generating them in Python keeps microsecond precision and
    behaves identically on SQLite and PostgreSQL.

    Inherit it explicitly on models that want timestamps; it is deliberately
    not applied to every model through Base.
    """

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
