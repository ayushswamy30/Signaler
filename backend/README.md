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
python -m app.seed            # optional: development accounts and conversations
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
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token signing. **Replace the secret before any real use** — anyone who knows it can forge a token for any account. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | How long a session may be idle before sign-in is required again |
| `MAX_FAILED_LOGINS`, `LOCKOUT_MINUTES` | Brute-force protection thresholds |
| `BCRYPT_ROUNDS` | Password hashing work factor (12 by default) |
| `MAX_PAGE_SIZE` | Ceiling on any list endpoint's page size |

## Run the server

```bash
uvicorn app.main:app --reload
```

- `http://127.0.0.1:8000/api/health` — liveness
- `http://127.0.0.1:8000/docs` — interactive API documentation
- `ws://127.0.0.1:8000/ws?token=<access token>` — the realtime socket

## Run the tests

```bash
pytest
```

286 tests: the health endpoint, metadata and migration wiring, the test-database
and foreign-key infrastructure, the seven models' database behaviour,
cross-model integration over the whole object graph, password hashing and token
handling, every service, the HTTP API, and the realtime socket.

There is also an end-to-end smoke test that starts uvicorn as its own process on
a throwaway database and drives it over real HTTP and a real WebSocket:

```bash
python -m scripts.smoke_e2e
```

It covers what the in-process test client cannot — the socket handshake, the
ASGI server, and the lifespan that binds the event loop — and exits non-zero on
the first failed check, so it is usable as a deployment gate.

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
| `make_user`, `alice`, `bob`, `carol` | Registered accounts (password in `tests.conftest.DEFAULT_PASSWORD`) |
| `authed` | Signs the client in as a given user |
| `live` (in `test_websocket.py`) | A client with the lifespan running, so socket broadcasts are delivered |

```python
def test_something(db_session):
    db_session.add(Thing(name="x"))
    db_session.commit()

def test_via_the_api(client):        # routes get the temporary database
    assert client.get("/api/health").status_code == 200
```

## Models

Seven tables. Full reasoning for each — nullability, uniqueness,
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
| `refresh_tokens` | `id`, unique `token_hash` | One live session; stores a hash, rotates on use |

Shared machinery lives in `app/models/`: `Base` (in `app/database/database.py`)
with its constraint naming convention, `TimestampMixin`, the `UtcDateTime`
column type, and the `sa_enum()` helper.

## Services

Business logic lives in `app/services/`, not in the routes. Every public
function takes the `Session` as its first argument and commits its own work, so
a caller — an HTTP route, a WebSocket handler, or a script — never has to know
whether an operation touched one table or four.

| Module | Owns |
| --- | --- |
| `user_service` | Registration, lookup, search, profile, password, presence |
| `auth_service` | Login, lockout, session issuing, refresh rotation, logout |
| `contact_service` | The directed contact graph |
| `conversation_service` | Membership, the conversation list, read state, muting |
| `message_service` | Sending, history paging, edits, deletion, delivery state |
| `group_service` | Group creation, membership, roles, leaving |

Services raise the errors in `app/core/errors.py` rather than `HTTPException`,
which is what keeps them usable outside HTTP. `app/api/errors.py` is the single
place that maps each one to a status code.

`conversation_service.require_participant` is the authorisation gate every
conversation-scoped operation passes through. It reports a conversation the
caller is not in as **not found**, not **forbidden**: telling an outsider that
conversation 42 exists but is closed to them would leak the shape of other
people's conversations.

## The realtime layer

`app/websocket/` holds three pieces:

- **`manager.py`** — the in-memory registry of live sockets, keyed by user. One
  user may hold several (two tabs, a phone), and all of them receive every
  event. Registry bookkeeping is synchronous and unlocked: every caller runs on
  the one event loop that owns the sockets, and a disconnecting handler must be
  able to deregister itself without awaiting, because teardown can run under
  cancellation where any await raises immediately.
- **`events.py`** — the event vocabulary, and `publish()`, which is safe to call
  from a synchronous HTTP route running in a worker thread. The application
  lifespan records the event loop so a broadcast can be handed back to it.
- **`routes.py`** — the `/ws` endpoint. The token arrives as a query parameter
  because the browser WebSocket API cannot set headers; access tokens are
  short-lived and refresh tokens never travel this way.

`broadcast.py` answers two questions in one place for each event: what it looks
like on the wire, and who its audience is.

## Seed data

```bash
python -m app.seed            # does nothing if the database already has users
python -m app.seed --reset    # delete the seeded data first
```

Seven accounts (`ayush`, `priya`, `maya`, `devsharma`, `rohan`, `aditi`,
`karan`), all with the password `signaler123`, wired into direct conversations
and two groups with history, replies, an edited message, unread threads and one
deliberately empty conversation. It refuses to run unless `ENVIRONMENT` is a
development value.

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

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`.
The backend job installs `requirements.txt` on Python 3.11, runs `pytest`,
applies the migrations, runs `alembic check` so the build fails if the models
and migrations have drifted apart, and finally runs the end-to-end smoke test
against a real uvicorn process. A second job typechecks and builds the
frontend.

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
