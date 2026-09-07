"""The /ws endpoint: one socket per client, carrying every live update.

The socket is a *notification* channel, not a second API. Sending, editing and
deleting all go over HTTP, where errors have status codes and retries are
ordinary; the socket carries only the things HTTP cannot push -- other people's
messages, typing, presence, receipts -- plus the two acknowledgements a client
must be able to send without a round trip (typing, read).
"""

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, ServiceError
from app.database.database import get_db
from app.models.message_status import DeliveryStatus
from app.models.user import User
from app.schemas.user import UserPublic
from app.services import auth_service, conversation_service, message_service, user_service
from app.websocket import broadcast, events
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Client -> server. A short list on purpose; anything that changes stored data
# other than read state goes through the REST API.
CLIENT_TYPING_START = "typing.start"
CLIENT_TYPING_STOP = "typing.stop"
CLIENT_MARK_READ = "message.read"
CLIENT_PING = "ping"


def _authenticate(db: Session, token: str) -> User:
    """Resolve the token from the query string.

    A query parameter rather than a header because the browser WebSocket API
    cannot set headers. The trade-off is that the token may appear in server
    logs, which is why access tokens are short-lived and refresh tokens never
    travel this way.
    """
    return auth_service.user_from_access_token(db, token)


async def _handle_client_event(db: Session, user: User, payload: dict[str, Any]) -> None:
    """Act on one message from a client.

    Runs the blocking database work in a worker thread: this coroutine owns the
    event loop that every other client's socket is waiting on, so a synchronous
    query here would stall all of them.
    """
    event_type = payload.get("type")
    conversation_id = payload.get("conversation_id")

    if event_type == CLIENT_PING:
        return

    if event_type in (CLIENT_TYPING_START, CLIENT_TYPING_STOP):
        if not isinstance(conversation_id, int):
            return
        # Membership is checked before echoing: without it, anyone could make
        # themselves appear to be typing in a conversation they are not in.
        await asyncio.to_thread(
            conversation_service.require_participant,
            db,
            conversation_id=conversation_id,
            user_id=user.id,
        )
        await asyncio.to_thread(
            broadcast.typing,
            db,
            conversation_id=conversation_id,
            user=user,
            is_typing=event_type == CLIENT_TYPING_START,
        )
        return

    if event_type == CLIENT_MARK_READ:
        if not isinstance(conversation_id, int):
            return
        changed = await asyncio.to_thread(
            message_service.mark_read,
            db,
            conversation_id=conversation_id,
            user_id=user.id,
            up_to_message_id=payload.get("up_to_message_id"),
        )
        await asyncio.to_thread(
            broadcast.message_status_changed,
            db,
            message_ids=changed,
            status=DeliveryStatus.READ,
        )
        return

    raise ServiceError(f"Unknown event type: {event_type!r}")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Annotated[Session, Depends(get_db)],
    token: str = Query(default="", description="Access token"),
) -> None:
    """Accept a client socket and pump events until it goes away.

    The session comes from the same ``get_db`` dependency the HTTP routes use,
    so it is closed when the connection ends and can be overridden in tests.
    One session serves the whole connection rather than one per event: a socket
    is long-lived, and a session per event would mean opening a connection on
    every keystroke of a typing indicator.
    """
    try:
        user = await asyncio.to_thread(_authenticate, db, token)
    except AuthenticationError:
        # Closed rather than rejected with a body: the handshake has no place
        # to put one, and 1008 is the "policy violation" code clients expect.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    first_connection = manager.connect(user.id, websocket)

    try:
        if first_connection:
            await asyncio.to_thread(user_service.set_presence, db, user, is_online=True)
            await asyncio.to_thread(broadcast.presence, db, user)

        # Anything sent while this user was away has now reached a device.
        delivered = await asyncio.to_thread(message_service.mark_delivered, db, user_id=user.id)
        await asyncio.to_thread(
            broadcast.message_status_changed,
            db,
            message_ids=delivered,
            status=DeliveryStatus.DELIVERED,
        )

        online = manager.online_users()
        await websocket.send_json(
            events.event(
                events.READY,
                user=UserPublic.model_validate(user).model_dump(mode="json"),
                online_user_ids=sorted(online),
            )
        )

        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                continue
            try:
                await _handle_client_event(db, user, payload)
            except ServiceError as exc:
                # A bad frame closes nothing: the client is told and the socket
                # stays up, because one malformed event is not a broken session.
                await websocket.send_json(events.event(events.ERROR, detail=exc.message))
            if payload.get("type") == CLIENT_PING:
                await websocket.send_json(events.event(events.PONG))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for user %s", user.id)
    finally:
        # Nothing here awaits. A closing socket is often being torn down under
        # cancellation, where the first await would raise and leave the user
        # marked online forever. The database work is small and runs inline on
        # the loop; the broadcast it triggers is scheduled, not awaited.
        if manager.disconnect(user.id, websocket):
            try:
                user_service.set_presence(db, user, is_online=False)
                broadcast.presence(db, user)
            except Exception:
                logger.exception("Failed to clear presence for user %s", user.id)
