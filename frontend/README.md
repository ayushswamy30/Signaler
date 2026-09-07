# Signaler Frontend

Next.js 15 (App Router) + TypeScript + Tailwind, implementing the design in
[`../design/`](../design/) against the live FastAPI backend.

## Run

```bash
cd frontend
npm install
cp .env.example .env.local     # points at the FastAPI backend
npm run dev                    # http://localhost:3000
```

The backend must be running and migrated first — see
[`../backend/README.md`](../backend/README.md). With `python -m app.seed` you can
sign in as `ayush` (or any seeded account) with the password `signaler123`.

`npm run build` and `npm run typecheck` both pass. There is no ESLint
configuration in this repository, so there is no `lint` script: `next lint` is
deprecated in Next 15 and prompts to set a linter up rather than running one.

## Routes

| Route | What it is |
| --- | --- |
| `/` | The app: conversation list, chat, replies, edits, group info, member management, voice and video calls |
| `/login` | Sign in against `POST /api/auth/login` |
| `/register` | Account creation, validating the same rules the API enforces |
| `/verify` | Phone verification — designed, not built; labelled as a placeholder |
| `/settings` | Profile, account (password, sign out), appearance, placeholder sections |

`/` and `/settings` redirect to `/login` without a session; `/login` and
`/register` redirect to `/` with one.

## How the data layer is arranged

Four files, each with one job, so that a backend change surfaces in exactly one
of them:

| File | Job |
| --- | --- |
| `src/lib/dto.ts` | The API's shapes, in its own snake_case |
| `src/lib/adapt.ts` | DTO → view model. The only place field names are translated |
| `src/lib/types.ts` | View models: camelCase, raw ISO timestamps |
| `src/lib/api.ts` | The HTTP client: base URL, tokens, refresh, one error type |

Timestamps stay as ISO strings all the way to the component, which then formats
them through `src/lib/format.ts`. Formatting on arrival would freeze "2 minutes
ago" at the moment the data was fetched.

`src/lib/socket.ts` is a plain class rather than a hook, because the connection
must outlive React's render cycle — a strict-mode double-effect must not tear
down a live socket. It reconnects with capped backoff and re-reads the access
token each attempt, so a refresh during a drop is picked up.

`src/lib/useMessenger.ts` holds the application state and subscribes to the
socket. An action calls the API, the API broadcasts, and the socket handler
applies the result — the same path whether the change originated on this device
or another one, which is what makes two browsers stay in step.

## Sessions

Tokens are kept in `localStorage`. That is a real trade-off — an httpOnly cookie
would be out of reach of any script on the page — but the backend is a separate
origin authenticated by a bearer header, and the socket needs the token as a
query parameter, so this code has to be able to read it either way. What limits
the damage is on the server: access tokens are short-lived, and refresh tokens
are single-use and rotate.

A 401 triggers one refresh attempt and one retry. Concurrent 401s queue behind a
single exchange, so a screen that fires four requests on mount spends one
refresh token rather than four.

## Optimistic sending

A sent message appears immediately with a temporary negative id, which cannot
collide with a server id. When the server confirms, the real message replaces
it. When it fails, the message stays on screen marked *Not delivered* with a
Discard action — text someone typed must never disappear because the network
did.

## Calls

`src/lib/call.ts` holds the WebRTC side: one peer connection, the media capture
that raises the browser's permission prompt, and the signalling handlers. The
overlay in `src/components/CallOverlay.tsx` is the ringing screen and the
in-call screen, full-screen and above everything — a ringing phone that can be
lost behind a window is a ringing phone you miss.

Details worth knowing before changing it:

- **Permission failures are translated.** `NotAllowedError`, `NotFoundError`,
  `NotReadableError` and `SecurityError` each become a sentence describing what
  to do; the browser's own "Requested device not found" explains nothing.
- **Early ICE candidates are buffered.** `addIceCandidate` throws before a
  remote description exists, and the first candidates routinely beat the answer,
  so they are held and replayed rather than dropped.
- **Teardown stops every track.** A `MediaStream` that is merely dereferenced
  leaves the camera light on, which reads — correctly — as still being watched.
- **Muting sets `track.enabled = false`** rather than stopping the track, so the
  negotiated session stays intact and unmuting needs no renegotiation.
- **The local preview is mirrored**, because people expect to see themselves as
  they do in a mirror, and it is muted, or you hear yourself echo.
- **Busy is decided here.** The server keeps no call state, so an incoming call
  that arrives while a peer connection exists is declined automatically.

## Tokens

`src/app/globals.css` defines every token as a CSS custom property under `:root`
and `[data-theme="dark"]`; `tailwind.config.ts` maps Tailwind's palette onto those
variables. Components never name a colour — `bg-surface`, `text-ink-muted`,
`bg-bubble-out` all resolve through the token layer, so dark mode is a single
attribute on `<html>` and nothing else changes.

The values match [`../design/design-tokens.md`](../design/design-tokens.md)
exactly, which is the same contract the Figma variables use.

## Accessibility

Carried over from the design brief, and worth preserving in review:

- **Delivery status never relies on colour** — sent, delivered, read and failed
  each render a different glyph, and each carries an `aria-label`.
- Message actions (reply, edit, delete) are hidden with `opacity`, not
  `display`, so they stay in the tab order and appear on focus.
- Focus is always visible (`:focus-visible` ring on the accent token).
- Mobile hit targets are at least 44px; desktop compacts to 34px.
- The message list is a `role="log"`, the typing indicator is `aria-live`, and
  connection and error banners are `role="status"` / `role="alert"`.
- A skip link precedes the app shell.

## Not built

Shown in the UI and labelled, rather than silently missing: phone verification,
profile photo upload, attachments, and the Privacy, Notifications, Calls and
Linked devices *settings* sections. Calling itself works — what is missing there
is a preferences screen for it (ringtone, default camera), not the feature.
