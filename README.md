# Signaler

A functional Signal Messenger clone, built as a full-stack engineering exercise
covering system design, APIs, real-time messaging, and user experience.

## Status

The backend foundation and database layer are in place. There is no frontend
yet, and no application API beyond the health endpoint — messaging,
authentication and real-time delivery come in later stages.

| Area | State |
| --- | --- |
| Backend foundation (FastAPI, config, CORS, health) | Done |
| Migrations (Alembic) | Done |
| Database layer and model conventions | Done |
| Models: `User`, `Contact`, `Conversation`, `ConversationParticipant` | Done |
| Models: `Message`, `MessageStatus` | Done |
| Database hardening: FK/index audit, cross-model integration tests | Done |
| Authentication, services, API endpoints, WebSockets | Not started |
| UI/UX design — tokens, design system, 21 screens | Done |
| Frontend (Next.js) | Not started |

149 tests pass; CI runs them on every pull request.

## Stack

- **Backend** — Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, pytest
- **Database** — SQLite (the schema is written to stay portable to PostgreSQL)
- **Frontend** — Next.js (planned)

## Layout

```
backend/
  app/
    main.py       application setup: CORS, router mounting
    core/         configuration
    api/          HTTP routes
    schemas/      Pydantic request/response contracts
    services/     business logic (empty, reserved)
    models/       SQLAlchemy models
    database/     engine, session factory, declarative Base
    websocket/    real-time infrastructure (empty, reserved)
  alembic/        migration environment and versions
  tests/          pytest suite
  docs/           model and schema conventions
.github/workflows/backend.yml   CI: pytest + alembic check
```

The backend is a modular monolith: one deployable service, with layers that
only depend downward — `api → services → database`.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head          # nothing creates the schema at startup
uvicorn app.main:app --reload # http://127.0.0.1:8000/api/health
pytest
```

The frontend design lives in [design/](design/): token spec in
[design-tokens.md](design/design-tokens.md), and the design system plus 21 screens
as a canvas built from [design/canvas/](design/canvas/).

Full backend documentation — configuration, migration commands, and how tests
get a database — is in [backend/README.md](backend/README.md). Schema decisions
are in [backend/docs/model-conventions.md](backend/docs/model-conventions.md).

## Data model

Six tables so far:

- **`users`** — accounts. Unique username, optional-but-unique phone number,
  password hash, presence.
- **`contacts`** — a directed link between two users. Composite key
  `(user_id, contact_user_id)`.
- **`conversations`** — direct and group conversations in one table,
  distinguished by a type enum.
- **`conversation_participants`** — membership as an association object,
  carrying role, join time and read position. Composite key
  `(conversation_id, user_id)`.
- **`messages`** — content, type, and an optional self-referential reply
  target. Indexed on `(conversation_id, created_at)` for history queries.
- **`message_status`** — per-recipient delivery state (`SENT`/`DELIVERED`/
  `READ`), one row per message and user.

## Engineering notes

A few decisions that shaped the codebase, explained in full in the
[model conventions](backend/docs/model-conventions.md):

- **Alembic owns the schema.** Nothing calls `Base.metadata.create_all()`, and
  no migration runs at application startup — schema changes are explicit and
  reviewable.
- **Tests run against real migrations.** Each test gets a temporary SQLite
  database built by the actual migrations, so a broken migration fails the
  suite rather than hiding behind `create_all()`.
- **Timestamps are UTC-aware everywhere.** A custom column type normalises the
  difference between SQLite (which drops timezones) and PostgreSQL.
- **Deletion semantics are decided per relationship.** Contacts cascade;
  conversation membership does not, so deleting an account cannot silently
  erase history from other people's conversations.
