"""Shared column types used by the ORM models.

These exist because SQLite and PostgreSQL disagree on two points that would
otherwise leak inconsistency into every model. Keeping the differences here
means the models themselves stay plain SQLAlchemy.
"""

import enum
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A datetime column that is always timezone-aware UTC in Python.

    SQLite has no native timezone support: it stores a datetime as a string and
    returns it naive, discarding any offset. PostgreSQL's TIMESTAMPTZ returns an
    aware value. Without normalisation the same column would yield naive values
    in development and aware values in production, and comparing the two raises
    TypeError.

    On the way in, values must be aware and are converted to UTC. On the way
    out, values are always returned as aware UTC.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "Naive datetime rejected; use datetime.now(timezone.utc) so the "
                "stored value is unambiguous."
            )
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        # SQLite returns naive values that are already UTC; PostgreSQL returns
        # aware values that may be in another zone.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


# Wide enough that adding a member later does not change the column type.
# The stored value is the enum's value string, so keep those reasonably short.
ENUM_LENGTH = 32


def sa_enum(python_enum: type[enum.Enum], *, name: str, **kwargs: Any) -> sa.Enum:
    """Build the project's standard column type for a Python enum.

    Enums are stored as a plain VARCHAR holding the member's value, not as a
    native database enum. Native enums do not exist on SQLite, and on PostgreSQL
    adding a value means ALTER TYPE, which cannot run in a normal migration
    transaction.

    No CHECK constraint is emitted (``create_constraint=False``, SQLAlchemy's
    default, stated here so the choice is visible). SQLAlchemy still rejects
    unknown values in Python on the way in and out. The trade-off is deliberate:
    a CHECK constraint would mean every new enum member requires a migration
    that rebuilds the entire table under SQLite's batch mode.

    The column length is fixed rather than derived from the longest member, so
    adding a member does not silently produce a schema diff.

    ``name`` is required: it labels the type and any constraint derived from it,
    and unnamed constraints cannot be altered on SQLite.
    """
    kwargs.setdefault("length", ENUM_LENGTH)
    return sa.Enum(
        python_enum,
        name=name,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        # Store the member value (e.g. "text"), not the member name (e.g. "TEXT").
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
        **kwargs,
    )
