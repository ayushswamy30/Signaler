# Model and metadata conventions

Conventions for the ORM models introduced from A02 onward. The goal is that
models read as ordinary SQLAlchemy; the only shared machinery is a naming
convention, one column type, and one mixin.

## One declarative Base

`app/database/database.py` defines the only `Base`. Models inherit from it and
never declare their own `DeclarativeBase`. `Base.metadata` is what Alembic
compares the database against, so a second base would be invisible to
migrations.

## Registering a model

A model attaches to `Base.metadata` only when its module is imported. Adding a
model is therefore two steps:

```python
# app/models/user.py
from app.database.database import Base

class User(Base):
    __tablename__ = "users"
    ...
```

```python
# app/models/__init__.py
from app.models.user import User

__all__ = ["User"]
```

`alembic/env.py` imports `app.models` before reading `Base.metadata`. **A model
not imported in `app/models/__init__.py` is invisible to autogenerate, and
Alembic will generate an empty migration without warning.**

## Naming convention

`Base.metadata` carries a `naming_convention` (defined in `database.py`) so every
index and constraint gets a deterministic name: `pk_users`,
`uq_users_email`, `fk_messages_sender_id_users`, `ix_messages_conversation_id`.

This is not cosmetic. SQLite cannot drop or alter an unnamed constraint, and
Alembic's batch mode rebuilds tables to work around that. Unnamed constraints
produce migrations that fail. The convention must not change once tables exist —
changing it renames every constraint in the database.

## Primary keys

Integer surrogate primary keys (`id`), autoincrementing, unless there is a
specific reason otherwise:

```python
id: Mapped[int] = mapped_column(primary_key=True)
```

Natural or composite keys are acceptable for pure association tables where the
pair is genuinely the identity.

## Foreign keys

Always explicit, always on the child (the "many") side, and always with an
explicit nullability decision:

```python
sender_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
)
```

Note that SQLite does **not** enforce foreign keys unless `PRAGMA foreign_keys=ON`
is set per connection. That pragma is not enabled yet; enable it when the first
real foreign key lands, otherwise `ondelete` is silently inert in development
while behaving differently on PostgreSQL.

## Relationships

Declare both sides with `back_populates` (not `backref`) so each side is visible
in the class it belongs to. State the direction explicitly:

```python
class Conversation(Base):
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")

class Message(Base):
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
```

Many-to-many goes through an explicit association model rather than a bare
`secondary` table whenever the association carries its own data (a role, a join
timestamp, a read cursor) — which in this project it usually will.

**Cascades are opt-in and deliberate.** Do not add
`cascade="all, delete-orphan"` reflexively. Decide per relationship whether a
parent's deletion should destroy children, and prefer soft deletion for anything
a user can see. Deleting a user should not silently erase message history in
other people's conversations.

## Timestamps

Use `TimestampMixin` from `app/models/mixins.py` for `created_at` / `updated_at`.
Inherit it only where both columns are wanted; it is not applied globally.

Values are generated in **Python**, not by the database:

- SQLite's `CURRENT_TIMESTAMP` has whole-second resolution — too coarse to order
  messages arriving in the same second. Python-side defaults keep microseconds.
- `onupdate` is an ORM-level hook, so it works the same on both backends.

Columns use `UtcDateTime` (`app/models/types.py`), which stores aware UTC and
returns aware UTC on every backend. Plain `DateTime(timezone=True)` returns
*naive* values from SQLite and *aware* values from PostgreSQL; comparing the two
raises `TypeError`. Naive datetimes are rejected on write rather than being
silently assumed to be UTC.

For a timestamp that is part of the domain (when a message was sent or read),
prefer an explicit column over reusing `created_at`.

## Enums

Python `enum.Enum` subclasses, given a column type via `sa_enum()`:

```python
class MessageType(enum.Enum):
    TEXT = "text"
    IMAGE = "image"

message_type: Mapped[MessageType] = mapped_column(
    sa_enum(MessageType, name="message_type"), nullable=False
)
```

Stored as `VARCHAR(32)` holding the member's **value** (`"text"`), with no
native database enum and no CHECK constraint. Rationale: native enums do not
exist on SQLite, and on PostgreSQL they require `ALTER TYPE` to extend; a CHECK
constraint would make every added member a full table rebuild under SQLite batch
mode. SQLAlchemy validates values in Python on read and write. The fixed length
means adding a member produces no schema diff.

## Nullability, uniqueness, indexes

- Set `nullable` explicitly on every column. Do not rely on the default.
- Put uniqueness in the database (`unique=True` or `UniqueConstraint`), not only
  in service code — concurrent requests defeat application-level checks.
- Add an index only for a query the code actually makes. Every index costs write
  throughput. Foreign keys used for lookups are the usual justified case.
