# Signaler Backend

FastAPI + SQLAlchemy + SQLite backend, organised as a modular monolith.

Run every command below from the `backend/` directory: the SQLite path, the
`.env` file, and `alembic.ini` are all resolved relative to it.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head          # create the database; nothing does this at startup
```

## Configuration

Settings come from the environment, read once by `app/core/config.py`. Copying
`.env.example` to `.env` gives working local defaults, so nothing needs editing
to get started. `.env` is gitignored and must never be committed.

| Variable | Purpose |
| --- | --- |
| `APP_NAME`, `ENVIRONMENT`, `DEBUG` | Application identity and debug mode |
| `DATABASE_URL` | SQLAlchemy URL; used by the app *and* by Alembic |
| `CORS_ORIGINS` | Comma-separated allowed origins for the Next.js dev server |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Placeholders for later authentication; unused today. Replace the secret before any real use. |

## Run the server

```bash
uvicorn app.main:app --reload    # http://127.0.0.1:8000/api/health
```

## Run the tests

```bash
pytest
```

149 tests: the health endpoint, metadata and migration wiring, the test-database
and foreign-key infrastructure, the six models' database behaviour, and
cross-model integration over the whole object graph.

## Testing against the database

Model tests use a temporary SQLite file, created per test and thrown away
afterwards, whose schema is built by running the real Alembic migrations.

- **Temporary database**: each test gets its own file under pytest's `tmp_path`,
  so tests cannot leak state into each other or into the developer's
  `signaler.db`. pytest deletes it; nothing lands in the repository.
- **Migrations, not `create_all()`**: building the schema from
  `Base.metadata.create_all()` would pass even if a migration were broken or
  never written. Running the migrations means the tests exercise the same
  pipeline that builds a real database, so a bad migration fails the suite.
- **A file, not `:memory:`**: each in-memory SQLite connection gets its own
  empty database, so the migrations would run in one connection and the test
  session would open another and find no tables.
- **Foreign keys**: SQLite ignores foreign keys unless
  `PRAGMA foreign_keys=ON` is set, and the setting is per-connection. The engine
  factory in `app/database/database.py` attaches it to every SQLite connection,
  so `ON DELETE` behaves in development the way it would on PostgreSQL instead
  of being silently inert. The pragma is attached per engine and only when the
  dialect is SQLite, so it never reaches a PostgreSQL engine.

Fixtures live in `tests/conftest.py`:

| Fixture | Gives you |
| --- | --- |
| `database_url` | URL of a temporary SQLite file |
| `migrated_engine` | Engine for that database with migrations applied |
| `db_session` | A `Session` bound to it — what most model tests want |
| `client` | `TestClient` whose `get_db` dependency yields `db_session` |

```python
def test_something(db_session):
    db_session.add(Thing(name="x"))
    db_session.commit()

def test_via_the_api(client):        # routes get the temporary database
    assert client.get("/api/health").status_code == 200
```

## Models

Four tables exist so far. Full reasoning for each — nullability, uniqueness,
deletion semantics, and which rules are deliberately left to the service layer
— is in [docs/model-conventions.md](docs/model-conventions.md).

| Table | Key | Purpose |
| --- | --- | --- |
| `users` | `id` | Accounts: unique username, optional-but-unique phone number, password hash, presence |
| `contacts` | `(user_id, contact_user_id)` | A directed saved link between two users |
| `conversations` | `id` | Direct and group conversations, split by a `ConversationType` enum |
| `conversation_participants` | `(conversation_id, user_id)` | Membership, carrying role, join time and read position |
| `messages` | `id` | A message in a conversation: content, type, optional reply target, edit/expiry timestamps |
| `message_status` | `id`, unique `(message_id, user_id)` | Per-recipient delivery state: `SENT` / `DELIVERED` / `READ` |

Shared machinery lives in `app/models/`: `Base` (in `app/database/database.py`)
with its constraint naming convention, `TimestampMixin`, the `UtcDateTime`
column type, and the `sa_enum()` helper.

Not yet built: authentication, services, and any API beyond `/api/health`.

### Adding a model

A model attaches to `Base.metadata` only when its module is imported, so
registration is two steps and the second is easy to forget:

1. Create `app/models/<name>.py` with a class inheriting from `Base`.
2. Import it in `app/models/__init__.py` and add it to `__all__`.

**A model missing from step 2 is invisible to autogenerate, which then produces
an empty migration with no error.** Tests in `tests/test_metadata.py` guard
against exactly that.

Then generate the migration, read it, and apply it — see below.

## Continuous integration

`.github/workflows/backend.yml` runs on every pull request and on pushes to
`main`: it installs `requirements.txt` on Python 3.11, runs `pytest`, applies
the migrations, and then runs `alembic check` so the build fails if the models
and migrations have drifted apart.

## Database migrations

The schema is managed exclusively by Alembic. Nothing creates tables at
application startup, so the database must be brought up to date explicitly.

Alembic reads its database URL from `app.core.config.settings.database_url` and
compares against `Base.metadata` from `app.database.database`, so it always
targets the same database and the same models as the running application.

Run all commands from the `backend/` directory:

```bash
# Apply all pending migrations (run this after cloning or pulling)
alembic upgrade head

# Create a new migration by comparing the models against the database
alembic revision --autogenerate -m "add users table"

# Create an empty migration to write by hand (e.g. data migrations)
alembic revision -m "backfill something"

# Roll back the most recent migration
alembic downgrade -1

# Roll back everything
alembic downgrade base

# Inspect state
alembic current      # revision the database is on
alembic history      # full migration history
alembic check        # fail if models have drifted from the database
```

Always review an autogenerated migration before committing it — Alembic detects
most changes but not all (notably some column renames, which it sees as a drop
plus an add).
