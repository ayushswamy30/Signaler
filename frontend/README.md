# Signaler Frontend

Next.js 15 (App Router) + TypeScript + Tailwind, implementing the design in
[`../design/`](../design/).

## Run

```bash
cd frontend
npm install
cp .env.example .env.local     # points at the FastAPI backend
npm run dev                    # http://localhost:3000
```

`npm run build`, `npm run typecheck` and `npm run lint` all pass.

## Routes

| Route | What it is |
| --- | --- |
| `/` | The app: sidebar, chat, reply, group info panel, new-message modal |
| `/login` | Sign in, with inline validation and error states |
| `/register` | Account creation with per-field validation |
| `/verify` | Six-box OTP entry with resend (demo code: `492715`) |
| `/settings` | Profile, appearance (light/dark), and the placeholder sections |

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
- Focus is always visible (`:focus-visible` ring on the accent token).
- Mobile hit targets are at least 44px; desktop compacts to 34px.
- The message list is a `role="log"`, the typing indicator is `aria-live`.
- A skip link precedes the app shell.

## What is not wired up yet

The backend currently exposes only `GET /api/health` — there are no auth,
conversation or message endpoints (those come in later stages). So screens render
from `src/lib/mock.ts` and the auth forms simulate their round trip. `next.config.ts`
already proxies `/api/*` to the FastAPI service, so swapping the mock module for
real `fetch` calls is the only change needed once those endpoints exist.

Sending a message optimistically walks `sent → delivered → read` on a timer,
standing in for the WebSocket that will drive it.
