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

SQLite does not enforce foreign keys unless `PRAGMA foreign_keys=ON` is set per
connection. This is now enabled for every SQLite connection by the engine
factory in `app/database/database.py`, so `ondelete` behaves in development the
way it will on PostgreSQL. Model tests get the same enforcement, because they
build their engine through that same factory.

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

## Models

### User (`app/models/user.py`)

A registered account, and the parent entity for contacts, conversation
participants and messages in later stages.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | Surrogate primary key, `pk_users` |
| `username` | `String(50)` | Required, unique (`uq_users_username`) |
| `phone_number` | `String(32)` | Optional, unique when present |
| `display_name` | `String(100)` | Required; the visible name |
| `avatar_url` | `String(512)` | Optional |
| `password_hash` | `String(255)` | Required; a hash, never a password |
| `is_online` | bool | Required, defaults to `False` |
| `last_seen` | `UtcDateTime` | Optional |
| `created_at` / `updated_at` | `UtcDateTime` | From `TimestampMixin` |

Decisions worth knowing:

- **`phone_number` is nullable but unique.** SQL treats NULLs as distinct in a
  unique constraint, so any number of accounts may have no phone number while a
  given number can still be claimed only once. No partial index is needed, and
  there is a test proving it — get this wrong and exactly one phoneless account
  is possible.
- **No explicit index on `username` or `phone_number`.** A unique constraint is
  already backed by a unique index, so `index=True` would only add a second,
  redundant index on the same column.
- **`password_hash` holds a hash and nothing else.** The model does no hashing
  and exposes no password helpers; that is the service layer's job.
- **Presence is not managed by the model.** `is_online` and `last_seen` have no
  `onupdate` hook, so an unrelated profile edit cannot silently mark someone
  online or move their last-seen time. Services and the WebSocket layer write
  them deliberately.
- **Timestamps follow the existing convention**: `TimestampMixin` for
  `created_at` / `updated_at`, `UtcDateTime` for `last_seen`, all
  Python-generated, aware UTC, microsecond precision.

### Contact (`app/models/contact.py`)

A directed link: `user_id` has saved `contact_user_id` as a contact. A saving B
says nothing about whether B has saved A — those are two independent rows.

| Column | Type | Notes |
| --- | --- | --- |
| `user_id` | int FK → `users.id` | Part of the primary key, `ON DELETE CASCADE` |
| `contact_user_id` | int FK → `users.id` | Part of the primary key, `ON DELETE CASCADE` |
| `created_at` | `UtcDateTime` | When the link was made |

Decisions worth knowing:

- **Composite primary key `(user_id, contact_user_id)`.** The pair *is* the
  identity of the row, so a surrogate `id` would add a column and an index
  without expressing anything. It also makes "A added B twice" a primary-key
  violation, so no separate unique constraint is needed — adding one over the
  same columns would only duplicate the index.
- **No `updated_at`.** A contact row records that a link was made; it is not
  edited afterwards, so `TimestampMixin` would add a column that never changes.
  `created_at` uses the same `UtcDateTime` + `utcnow` convention the mixin does.
- **Both foreign keys cascade on delete.** A contact row is meaningless once
  either participant is gone, so deleting a user removes both the contacts they
  saved and the contacts pointing at them. The cascade lives in the *database*,
  not only in relationship configuration, so rows cannot survive a delete that
  bypasses the ORM.
- **Two relationships, deliberately distinct names.** `user.contacts` is the
  people this user saved; `user.contact_of` is the rows where this user is the
  saved contact. Both foreign keys point at `users.id`, so SQLAlchemy cannot
  infer which one each relationship travels — `foreign_keys=` is required, not
  optional. Both use `passive_deletes=True` so the database performs the
  cascade rather than the ORM loading every row to delete it.
- **Self-contact is an application rule, not a database invariant.** Nothing
  stops `A → A` at the database level today; there is no CHECK constraint, and
  the model test documents that honestly rather than implying a guard that does
  not exist. The Contacts service must reject it when that layer is built.

### Conversation and ConversationParticipant

One `conversations` table serves both direct and group conversations,
distinguished by `ConversationType` (`DIRECT` / `GROUP`). Separate tables would
duplicate the participant, message and read-state machinery for no gain, since
everything below a conversation is identical either way.

**conversations**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | Primary key |
| `type` | `ConversationType` | Required; `direct` or `group` |
| `name` | `String(100)` | Optional; groups are named, direct ones are labelled by the other participant |
| `avatar_url` | `String(512)` | Optional |
| `created_at` / `updated_at` | `UtcDateTime` | From `TimestampMixin` |

**conversation_participants**

| Column | Type | Notes |
| --- | --- | --- |
| `conversation_id` | int FK → `conversations.id` | Part of the primary key, `ON DELETE CASCADE` |
| `user_id` | int FK → `users.id` | Part of the primary key, `ON DELETE RESTRICT`, indexed |
| `role` | `ParticipantRole` | Required, defaults to `MEMBER` |
| `joined_at` | `UtcDateTime` | When the user joined |
| `last_read_message_id` | int | Nullable, **no foreign key yet** |

Decisions worth knowing:

- **Participants are an association object, not a plain many-to-many.** The
  membership carries its own state — role, join time, read position — so there
  is no `User.conversations` shortcut; hiding the association behind a
  many-to-many would obscure the thing callers actually need.
- **Composite primary key `(conversation_id, user_id)`**, the same pattern as
  `Contact`: a user cannot join the same conversation twice, enforced by the
  key rather than a separate unique constraint.
- **Deleting a conversation cascades to its participants**; membership cannot
  outlive its conversation.
- **Deleting a user is RESTRICTed, not cascaded.** Removing an account must not
  silently erase its membership of a group conversation, which is part of that
  conversation's history for everyone else. The database refuses the delete
  while membership exists, so account deletion has to be designed rather than
  defaulting to destruction. **The account-deletion strategy (tombstone or soft
  delete) is an open decision** — `User` was deliberately not changed here.
- **`last_read_message_id` is a bare integer** until the `Message` model
  exists. Adding a placeholder Message model just to satisfy the foreign key
  would be worse than waiting; a later migration adds the reference to
  `messages.id`.
- **`user_id` is indexed.** The composite primary key already covers lookups
  starting with `conversation_id` ("who is in this conversation?"), but not
  ones starting with `user_id` ("every conversation this user is in") — the
  query behind the conversation list, on the app's main screen.
- **Direct-conversation uniqueness is a service-layer invariant.** Participants
  live in a child table, so no column constraint can express "this pair
  already has a direct conversation". The schema permits duplicates; the
  `ConversationService` must look for an existing `DIRECT` conversation
  containing exactly those two users before creating one. This is deliberate,
  not an oversight, and a test records the current behaviour honestly.
- **Conversation shape and group role rules are service-layer invariants too**
  — that a direct conversation has exactly two participants, that a group has a
  name, that a group keeps at least one admin. Encoding them in the schema
  would make ordinary steps impossible, since a conversation must exist before
  its participants can reference it. `ADMIN` and `MEMBER` are structural only;
  no authorisation logic lives in the model.

### Message and MessageStatus

**messages**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | Primary key |
| `conversation_id` | int FK → `conversations.id` | Required, `ON DELETE CASCADE` |
| `sender_id` | int FK → `users.id` | Required, `ON DELETE RESTRICT`, indexed |
| `content` | `Text` | Required; not validated here |
| `message_type` | `MessageType` | Required; only `TEXT` today |
| `reply_to_id` | int FK → `messages.id` | Nullable, `ON DELETE SET NULL`, indexed |
| `created_at` | `UtcDateTime` | Required |
| `edited_at` / `expires_at` | `UtcDateTime` | Nullable; written by services, never by the model |

**message_status** — one row per (message, recipient)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | Primary key |
| `message_id` | int FK → `messages.id` | Required, `ON DELETE CASCADE` |
| `user_id` | int FK → `users.id` | Required, `ON DELETE RESTRICT`, indexed |
| `status` | `DeliveryStatus` | Required; `SENT` / `DELIVERED` / `READ` |
| `updated_at` | `UtcDateTime` | Required; advances on update |

Decisions worth knowing:

- **Deletion flows down, never sideways into accounts.** Deleting a
  conversation deletes its messages, and deleting a message deletes its status
  rows — a two-level cascade. Deleting a *user* does neither: both
  `messages.sender_id` and `message_status.user_id` are `RESTRICT`, so the
  database refuses rather than erasing what someone said in other people's
  conversations. This matches `ConversationParticipant.user_id`.
- **Account deletion remains unresolved**, and now has three tables blocking
  it. A tombstone or soft-delete design is needed before real account deletion
  can work; `User` was deliberately not changed here.
- **`reply_to_id` is `SET NULL`, not `RESTRICT`.** A reply is history and must
  outlive the message it answers, so the pointer is simply cleared. `RESTRICT`
  would also have made any conversation containing a reply impossible to
  delete, because the cascade would hit messages referencing each other —
  verified against SQLite before choosing.
- **`MessageStatus` uses a surrogate primary key with a unique constraint on
  `(message_id, user_id)`**, unlike `Contact` and `ConversationParticipant`,
  which use composite primary keys. Those are pure associations that nothing
  references, so the pair is their identity. A status row is a mutable entity
  with its own lifecycle, so a single-column key keeps it addressable; the
  unique constraint supplies the same duplicate protection.
- **`last_read_message_id` stays a plain integer.** Now that `messages` exists
  the foreign key *could* be added, but doing so is its own migration and its
  own decision, not a side effect of this stage. A retargeted test guards that.
- **Message history is ordered by `created_at`**, and the composite index
  `(conversation_id, created_at)` serves the whole query
  `WHERE conversation_id = ? ORDER BY created_at` — filter and sort together.
  A plain `conversation_id` index would leave a sort behind it.
- **Other indexes**: `sender_id` and `message_status.user_id` back the
  `RESTRICT` checks, which otherwise scan the whole table on every user
  deletion; `reply_to_id` backs both the `replies` relationship and the
  `SET NULL` sweep when a message is deleted. No speculative indexes.
- **Rules the model does not enforce**: empty content, edit permissions,
  expiry, and status progression (nothing stops `READ` going back to `SENT`).
  All service-layer concerns.
