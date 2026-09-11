"""The realtime event vocabulary, and the bridge from sync code into it.

HTTP routes run in a worker thread (FastAPI runs sync handlers off the event
loop) while the connection manager is async and lives on the loop. ``publish``
is the crossing point: it is safe to call from either side, so a route can
announce a new message with one ordinary function call.
"""

import asyncio
import logging
from typing import Any

from app.websocket.manager import manager

logger = logging.getLogger(__name__)

# Server -> client event names. Grouped by subject and dotted, so a client can
# switch on the prefix; kept as constants so a typo is an AttributeError here
# rather than an event nobody ever receives.
READY = "ready"
PONG = "pong"
ERROR = "error"

MESSAGE_NEW = "message.new"
MESSAGE_UPDATED = "message.updated"
MESSAGE_DELETED = "message.deleted"
MESSAGE_STATUS = "message.status"

TYPING_START = "typing.start"
TYPING_STOP = "typing.stop"

PRESENCE = "presence"

# Call signalling. The server relays these between peers and stores none of
# them; see app/websocket/calls.py.
CALL_INCOMING = "call.incoming"
CALL_ACCEPTED = "call.accepted"
CALL_CANDIDATE = "call.candidate"
CALL_ENDED = "call.ended"
CALL_UNAVAILABLE = "call.unavailable"
# Group calls only. A group call is a mesh: every pair negotiates its own
# connection, so "someone joined" is separate from "here is an offer for you".
CALL_JOINED = "call.joined"
CALL_PEER_OFFER = "call.peer_offer"
CALL_PEER_ANSWER = "call.peer_answer"

CONVERSATION_CREATED = "conversation.created"
CONVERSATION_UPDATED = "conversation.updated"
CONVERSATION_DELETED = "conversation.deleted"
GROUP_MEMBERS_ADDED = "group.members_added"
GROUP_MEMBER_REMOVED = "group.member_removed"
GROUP_ROLE_CHANGED = "group.role_changed"

# Set once, when the application starts, by app.main's lifespan. Without it a
# background thread has no loop to hand work to.
_loop: asyncio.AbstractEventLoop | None = None


def bind_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Record the loop that owns the WebSocket connections."""
    global _loop
    _loop = loop


def clear_event_loop() -> None:
    """Forget the loop on shutdown, so a stale one is never scheduled onto."""
    global _loop
    _loop = None


def event(name: str, **data: Any) -> dict[str, Any]:
    """Build the envelope every event travels in.

    A flat ``{"type": ..., **data}`` was tempting, but a nested payload means a
    field named "type" inside an event can never collide with the envelope.
    """
    return {"type": name, "data": data}


def publish(user_ids: list[int] | set[int], payload: dict[str, Any]) -> None:
    """Send an event to a set of users, from sync or async code.

    Fire-and-forget by design: a failed delivery must never turn a successful
    HTTP request into an error, because the message is already committed. The
    client reconciles on its next fetch.
    """
    if not user_ids:
        return

    coroutine = manager.send_to_users(user_ids, payload)
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        # Already on the loop (a WebSocket handler): schedule and move on.
        running.create_task(coroutine)
        return

    if _loop is None or _loop.is_closed():
        # No live application loop -- the ordinary case under the test client
        # for pure-HTTP tests. Closing the coroutine avoids a "never awaited"
        # warning that would otherwise look like a bug.
        coroutine.close()
        return

    asyncio.run_coroutine_threadsafe(coroutine, _loop)
