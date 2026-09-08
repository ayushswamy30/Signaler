# Signaler

A working Signal Messenger clone: a FastAPI backend with real-time WebSocket
delivery, and a Next.js client that talks to it. Registration, sign-in, direct
and group conversations, replies, edits, deletions, typing indicators, presence,
delivery receipts, read state, emoji and stickers, and one-to-one voice and
video calls all work end to end against the real server.

## Status

| Area | State |
| --- | --- |
| Backend foundation (FastAPI, config, CORS, health) | Done |
| Migrations (Alembic) and database layer | Done |
| Models: users, contacts, conversations, participants, messages, status, sessions | Done |
| Services: users, auth, contacts, conversations, messages, groups | Done |
| REST API: auth, users, contacts, conversations, messages, groups | Done |
| Authentication: bcrypt, JWT access tokens, rotating refresh tokens, lockout | Done |
| WebSockets: messages, typing, presence, receipts, group events | Done |
| Voice and video calls (WebRTC, one-to-one, TURN fallback) | Done |
| Emoji picker and sticker sends | Done |
| Development seed data | Done |
| UI/UX design — tokens, design system, 21 screens | Done |
| Frontend: auth, chat, groups, contacts, settings, dark mode, responsive | Done |

**301 backend tests** and a **30-check end-to-end smoke test** against a live
server pass; CI runs both, plus the frontend typecheck and build, on every pull
request.

## Stack

- **Backend** — Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, pytest
- **Auth** — bcrypt password hashing, JWT access tokens, opaque rotating refresh tokens
- **Database** — SQLite in development, PostgreSQL when deployed; the same models and migrations build both
- **Frontend** — Next.js 15 (App Router), TypeScript, Tailwind CSS

## Quick start

Two terminals. Backend first:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head          # nothing creates the schema at startup
python -m app.seed            # seven accounts with conversations and history
uvicorn app.main:app --reload # http://127.0.0.1:8000/docs
```

Then the client:

```bash
cd frontend
npm install
cp .env.example .env.local    # points at the FastAPI backend
npm run dev                   # http://localhost:3000
```

Sign in as any seeded account — `ayush`, `priya`, `maya`, `devsharma`, `rohan`,
`aditi`, `karan` — with the password `signaler123`. Open two browsers signed in
as different people to watch messages, typing and presence move between them
live.

## Layout

```
frontend/
  src/app/          routes: chat, login, register, verify, settings
  src/components/   Avatar, Button, Chat, Composer, Sidebar, Modal, CallOverlay,
                    PeoplePicker, ConversationInfo, EmojiPicker, CursorWave,
                    Icon, ThemeToggle, NewGroupModal, NewMessageModal
  src/lib/          api client, socket, auth context, state hook, adapters,
                    call (WebRTC), emoji/sticker logic, DTO types, formatting
backend/
  app/
    main.py         application setup: CORS, routers, lifespan
    core/           configuration, security (hashing, tokens), service errors
    api/            HTTP routes, dependencies, error-to-status mapping
    schemas/        Pydantic request/response contracts
    services/       business logic — the layer that owns the rules
    models/         SQLAlchemy models
    database/       engine, session factory, declarative Base
    websocket/      connection registry, event vocabulary, call signalling, /ws endpoint
    seed.py         development data
  alembic/          migration environment and versions
  scripts/          smoke_e2e.py — live-server end-to-end test
  tests/            pytest suite
  docs/             model and schema conventions
.github/workflows/ci.yml   CI: pytest, alembic check, smoke test, frontend build
```

The backend is a modular monolith: one deployable service, with layers that
only depend downward — `api → services → models → database`. The WebSocket
layer sits beside the API and calls the same services, so a message sent over
HTTP and one sent by a script take the same path through the rules.

## How it fits together

Sending a message is the shape of every write in this system:

1. The client `POST`s to `/api/conversations/{id}/messages`.
2. The route calls `message_service.send_message`, which checks membership,
   validates the content, stores the message, and creates one delivery-status
   row per recipient.
3. The route then calls `broadcast.message_created`, which serialises the
   message once and publishes it to every participant's live sockets.
4. Each client applies the event. The sender's own devices receive it too, so a
   message typed on a phone appears on a laptop with the same server-assigned
   id.

Authorisation lives in the services, not the routes, which is why the same rule
holds however the operation is reached. A conversation the caller is not in is
reported as **not found** rather than **forbidden** — telling an outsider that
conversation 42 exists would leak the shape of other people's conversations.

## API

Everything except `/api/health` and the `/api/auth` entry points needs a bearer
access token. Full interactive documentation is at `/docs` when the server runs.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/auth/{register,login,refresh,logout,logout-all}`, `GET /api/auth/me` |
| Users | `GET/PATCH /api/users/me`, `POST /api/users/me/password`, `GET /api/users/search`, `GET /api/users/{id}` |
| Contacts | `GET/POST /api/contacts`, `DELETE /api/contacts/{id}` |
| Conversations | `GET /api/conversations`, `POST /api/conversations/direct`, `GET /api/conversations/{id}`, `/members`, `/messages`, `POST .../read`, `PATCH .../mute` |
| Messages | `PATCH/DELETE /api/messages/{id}` |
| Groups | `POST /api/groups`, `PATCH /api/groups/{id}`, `POST/DELETE/PATCH .../members`, `POST .../leave` |
| Realtime | `ws://…/ws?token=…` — messages, typing, presence, receipts, call signalling |

The socket is a notification channel, not a second API: writes go over HTTP,
where errors have status codes and retries are ordinary. It carries only what
HTTP cannot push — other people's messages, typing, presence, receipts — plus
the acknowledgements a client must send without a round trip (typing, read) and
call signalling, which has nowhere else to live.

The socket reconnects automatically with exponential backoff (500 ms to 15 s).
Call-signalling messages sent while the socket is down are queued and flushed in
order when it reopens, because a lost `call.accept` or `call.candidate` silently
breaks a call with no way to detect or retry. Everything else — typing and read
receipts — is dropped rather than queued, since a replayed backlog of stale
indicators would be worse than silence.

## Calls

One-to-one voice and video, over WebRTC. The server relays two small JSON blobs
— a session description and a stream of network candidates — and then gets out
of the way: the audio and video flow directly between the two browsers and never
touch the backend. That is why calls run at full quality on a free-tier instance
that could never carry video itself.

The microphone and camera are requested through `getUserMedia`, which is what
raises the browser's permission prompt. It runs before any negotiation, because
there is no point connecting a call someone cannot speak into, and each way it
can fail — permission refused, no device, device already in use, insecure
origin — is reported as something the person can act on rather than as the
browser's own wording.

ICE diagnostic reporting prints exactly what was gathered, received, and
nominated when a call fails, separating the three distinct causes (TURN
credentials rejected, relay works but peers still can't meet, or a non-network
problem) so a failure has a reason rather than just "failed". Transient
`disconnected` states — common on mobile — are tolerated for up to 30 seconds
before ending the call, and each new call tears down the previous peer
connection cleanly so stale ICE candidates from an earlier session cannot
contaminate a fresh one.

Two limits are structural, not oversights:

- **One-to-one only.** A group call needs a mesh of N×(N−1) peer connections or
  a media server to mix the streams. The backend refuses group conversations
  outright, and the UI hides the call buttons there, rather than half-connecting
  three people.
- **TURN is a free relay, not a paid one.** Public STUN alone is enough on
  most home and office networks, but not behind symmetric NAT or a strict
  corporate/carrier firewall, where the two peers cannot address each other at
  all and the media needs relaying through a TURN server — two ordinary phones
  on two different mobile carriers hit this routinely. The client falls back
  to Open Relay Project's free, keyless TURN server so those calls connect
  rather than dying at "Connecting…" with no audio or video either way; its
  bandwidth is shared and rate-limited, so a paid TURN provider is the
  production-grade version of this same fix.

## Emoji and stickers

The composer has a curated emoji picker and a sticker tray, hand-rolled rather
than a multi-megabyte package (keeping with the rest of the UI, where every icon
is a hand-drawn SVG — see `Icon.tsx`). Emoji augment whatever is being typed:
picking one inserts it at the cursor and leaves the picker open for more. A
sticker *is* the message — picking one sends it immediately and closes the
picker, the way a sticker tray works in every mainstream messenger.

The distinction between a sticker send and an emoji-only message someone typed is
carried in the message content itself (a zero-width space prefix, invisible in
every display context) rather than inferred from shape, because an earlier
version that guessed made every short "👍" indistinguishable from a tapped
sticker.

## Data model

Seven tables:

- **`users`** — accounts. Unique username, optional-but-unique phone number,
  password hash, presence, and brute-force state.
- **`contacts`** — a directed link between two users. Composite key
  `(user_id, contact_user_id)`.
- **`conversations`** — direct and group conversations in one table,
  distinguished by a type enum.
- **`conversation_participants`** — membership as an association object,
  carrying role, join time, mute flag and read position. Composite key
  `(conversation_id, user_id)`.
- **`messages`** — content, type, and an optional self-referential reply
  target. Indexed on `(conversation_id, created_at)` for history queries.
- **`message_status`** — per-recipient delivery state (`SENT`/`DELIVERED`/
  `READ`), one row per message and user.
- **`refresh_tokens`** — one row per live session, storing a hash rather than
  the token, revoked on rotation.

## Engineering notes

Decisions that shaped the codebase; the schema reasoning is in full in
[backend/docs/model-conventions.md](backend/docs/model-conventions.md).

- **Alembic owns the schema.** Nothing calls `Base.metadata.create_all()`, and
  no migration runs at application startup — schema changes are explicit and
  reviewable.
- **Tests run against real migrations.** Each test gets a temporary SQLite
  database built by the actual migrations, so a broken migration fails the
  suite rather than hiding behind `create_all()`.
- **Services raise, routes translate.** Business logic raises plain Python
  errors, and one module maps them to status codes, so the same service is
  usable from the socket and from a script.
- **Refresh tokens rotate and are stored hashed.** Each is single-use, so a
  stolen copy stops working the moment either party uses it, and a database
  leak hands out no live sessions.
- **Timestamps are UTC-aware everywhere.** A custom column type normalises the
  difference between SQLite (which drops timezones) and PostgreSQL.
- **Deletion semantics are decided per relationship.** Contacts and sessions
  cascade; conversation membership and messages do not, so deleting an account
  cannot silently erase history from other people's conversations.

## Deploying

The client and the API are hosted separately, because FastAPI's WebSockets need
a long-lived process and cannot run on Vercel's serverless functions.

| Piece | Host | Configuration |
| --- | --- | --- |
| Frontend | Vercel | `NEXT_PUBLIC_API_URL` = the backend's URL. Inlined at build time, so changing it needs a redeploy. |
| Backend + database | Render | Defined by [`render.yaml`](render.yaml). Set `CORS_ORIGINS` to the frontend's origin. |

If `NEXT_PUBLIC_API_URL` is not set, the built bundle falls back to
`http://127.0.0.1:8000` — the visitor's own machine — and every request fails in
their browser with "Cannot reach the server". That fallback is right for local
development and wrong everywhere else, which is why the deploy sets it
explicitly.

The deployed backend runs on Postgres rather than SQLite: a free instance has an
ephemeral filesystem, so a SQLite file would be lost on every restart along with
every account in it. Nothing in the application changes between the two —
`Settings.sqlalchemy_url` normalises the provider's `postgres://` URL to the
psycopg driver, and the same migrations build both schemas.

Verify a deployment with the same scenario the local suite runs:

```bash
cd backend
SMOKE_BASE_URL=https://<your-service>.onrender.com python -m scripts.smoke_e2e
```

## Known limits

Deliberate, and listed so they are not mistaken for oversights:

- **Not end-to-end encrypted.** Messages are stored in plain text. The Signal
  protocol is the one part of Signal this clone does not attempt.
- **Single process.** The socket registry is in memory, so a second worker
  would not see the first one's connections. `ConnectionManager.send_to_users`
  is the seam where a Redis pub/sub broker would slot in.
- **Text messages only.** Attachments and voice notes are not implemented; the
  message type column is sized to accept them later without a schema change.
  Emoji and stickers are plain-text messages.
- **Calls are not recorded or logged.** No call history, no missed-call entry in
  the conversation — the server keeps no call state at all, by design.
- **Phone verification and photo upload are placeholders**, shown in the UI and
  labelled as such.
- **A free-tier deployment sleeps.** After 15 minutes without traffic the
  instance stops; the next request takes roughly a minute to wake it, and open
  WebSockets drop in the meantime. The client reconnects on its own, but live
  delivery pauses while the server is asleep.

The design lives in [design/](design/): the token spec in
[design-tokens.md](design/design-tokens.md), and the design system plus 21
screens as a canvas built from [design/canvas/](design/canvas/).
