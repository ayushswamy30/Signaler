# Group voice and video calls

**Status:** implemented and verified end to end (three real browsers, live mesh).

## The problem

Group chats had no call buttons. That was not an oversight in the UI — the
whole call path was scoped to one-to-one conversations:

- `backend/app/websocket/calls.py` raised `"Calls are only supported in
  one-to-one conversations."` for any frame naming a group.
- `frontend/src/components/Chat.tsx` hid the phone and video buttons for
  groups, with a comment saying a group call needs a media server.
- `frontend/src/lib/call.ts` held exactly one `RTCPeerConnection` and one
  remote stream, so even an unlocked backend had nothing to connect to.

Exposing the two buttons alone would have produced a call that rings and then
fails. What follows is the actual multi-party implementation.

## The shape: a mesh, not a media server

A group call here is a **mesh**. Every pair of people in the call negotiates its
own peer connection, so a call of N people is N×(N−1)/2 connections and each
person uploads their camera N−1 times.

The alternative is an SFU — a media server that receives each stream once and
forwards it. That is the right answer for large calls, and the wrong answer
here: it would put every participant's video through the backend, which is the
exact cost the existing one-to-one design was built to avoid (media flows
browser-to-browser; a free-tier instance never carries a frame). The mesh keeps
that property. Its price is that it degrades with group size, which is stated
in the README as a structural limit rather than left to be discovered.

## Who offers? Settling negotiation with no server state

The server stores nothing about calls — no ringing table, no membership of a
call in progress — because such state is lost on restart and wrong the moment a
second worker exists. So the clients have to work out among themselves who
connects to whom, and do it without both sides offering at once (glare).

The rule is:

1. Placing a call sends `call.invite`, which rings **everyone else** in the
   conversation. It carries no SDP: each pair needs a different offer, and none
   of them exist yet.
2. Answering sends `call.accept`, which the server fans out to the whole
   conversation as `call.joined` — not just to the caller, because everyone
   already in the call needs to connect to the new arrival, and the server does
   not know who that is.
3. On hearing `call.joined` from someone you are not already connected to:
   **the lower user id sends the offer.** If you are the higher id, you
   re-announce yourself instead — because that person joined before you and has
   never seen you in an announcement, so they cannot offer until you say you are
   here. Anyone who already holds a connection to you ignores the re-announcement,
   so it settles rather than echoes.
4. The pair then exchanges `call.offer` / `call.answer` / `call.candidate`,
   each carrying `target_user_id`.

Every pair therefore connects exactly once, in one direction, with no glare and
no server-side coordination.

## What changed

### Backend

`app/websocket/calls.py`
- `_peer_id` (which refused groups) became `_others`, returning the
  conversation type and every other participant. Membership is still re-checked
  on every frame.
- `call.invite` rings every reachable participant; `call.unavailable` is
  returned only when *nobody* else is online. SDP is validated before presence
  is consulted, so a malformed frame is refused as malformed rather than
  reported back as "nobody is online".
- `call.accept` in a group is fanned out as `call.joined`; in a one-to-one it
  still carries the answer to the caller, unchanged.
- New addressed frames `call.offer` / `call.answer` relay per-pair SDP, and
  `call.candidate` now takes a `target_user_id` in groups. Every target is
  checked against the membership list — without that, a member could push
  candidates at any account id they could guess. The new frames are refused in
  one-to-one conversations, where the negotiation rides on the invite and the
  accept and a stray offer would be answering nothing.
- `call.decline` / `call.hangup` go to everyone in a group, carrying
  `from_user_id`, so each client drops just that one connection.

`app/websocket/events.py` — added `call.joined`, `call.peer_offer`,
`call.peer_answer`.

### Frontend

`src/lib/call.ts` — the single `RTCPeerConnection` became a map of peers keyed
by user id, so a one-to-one call is now simply the mesh with one peer and both
kinds of call run the same code. Consequences:

- Held ICE candidates are keyed per peer instead of globally, which also fixes
  the shape of the existing one-to-one buffering (candidates routinely arrive
  before the connection they belong to exists).
- A device change replaces the track on **every** connection — replacing it on
  one would leave the other participants watching a frozen frame.
- `failed` on one connection in a group drops that person and leaves the call
  running; in a one-to-one it still ends the call with an ICE diagnostic. The
  30-second "Reconnecting…" backstop stays one-to-one only: in a mesh, one peer
  stalling is not the call stalling.
- `useCall` now takes the current user id, which is what the offer rule needs.

`src/components/CallOverlay.tsx` — a group renders a tile grid (one per person,
with their name and a "Connecting…" state) instead of one full-bleed video. A
grid rather than a promoted speaker because the call has no basis on which to
pick one. Every tile carries its own media element even in a voice call: in a
mesh there is one audio track per person, not one for the call.

`src/components/Chat.tsx` — the call buttons are shown for groups, labelled
"Start group voice call" / "Start group video call".

`src/app/page.tsx` — `startCall` no longer requires a single counterpart.

## Verification

Backend: 311 tests pass. `tests/test_calls.py` replaces the old
"groups are refused" test with five covering the new relay — the invite ringing
everyone with no SDP, an accept reaching the whole conversation, an addressed
offer reaching only its named peer, a fabricated or self-naming target being
refused, and a hangup reaching everyone.

Frontend: `tsc --noEmit` and `next build` clean.

End to end, with three Chromium browsers against a live backend:

- Alice starts a group video call; Bob and Carol both ring and answer. All six
  connections come up and **each browser plays two remote streams**, with the
  right names on the right tiles.
- Run again with the accept order reversed, to exercise the re-announce branch
  of the offer rule. Same result.
- Carol hangs up: her tile disappears for Alice and Bob, and their call keeps
  running. (A group call outliving any one person leaving it is the point.)
- One-to-one regression: Dana calls Evan, the call connects, the in-call timer
  runs, and hanging up clears the overlay on both ends.

## Not done

- **Large calls.** See the mesh limit above; an SFU is the answer and is out of
  scope.
- **Ringing state in the sidebar.** A call in progress is not advertised in the
  conversation list, so someone who declines cannot re-join from the UI without
  a fresh invite.
- **A participant cap.** Nothing stops a call being placed in a 50-person
  group, where the mesh would not cope. A cap belongs here before this ships to
  real groups of that size.
