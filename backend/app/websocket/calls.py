"""Call signalling: the relay that lets two browsers negotiate a direct call.

The server carries no audio or video. WebRTC peers exchange a session
description and a list of network candidates, and once they agree the media
flows between the two devices directly -- so this module only forwards small
JSON blobs between two people who already share a conversation, and forgets
them immediately.

No call state is stored. A ringing table held in memory would be lost on every
restart and would be wrong the moment a second worker existed, so "is the other
person reachable" is answered from live socket presence, and "am I already on a
call" is answered by the client, which is the only party that actually knows.
"""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models.conversation import ConversationType
from app.models.user import User
from app.schemas.user import UserPublic
from app.services import conversation_service
from app.websocket import events
from app.websocket.manager import manager

# Client -> server.
CLIENT_INVITE = "call.invite"
CLIENT_ACCEPT = "call.accept"
CLIENT_DECLINE = "call.decline"
CLIENT_HANGUP = "call.hangup"
CLIENT_CANDIDATE = "call.candidate"

CLIENT_EVENTS = frozenset(
    {CLIENT_INVITE, CLIENT_ACCEPT, CLIENT_DECLINE, CLIENT_HANGUP, CLIENT_CANDIDATE}
)

CALL_TYPES = frozenset({"audio", "video"})

# An offer with a long candidate list runs to a few kilobytes; this is generous
# for that and still small enough that the signalling channel cannot be used to
# push arbitrary payloads between accounts.
MAX_SIGNAL_BYTES = 32_768


def _checked_blob(value: Any, field: str) -> dict[str, Any]:
    """Validate one opaque WebRTC payload.

    The contents are deliberately not interpreted -- SDP and ICE candidate
    shapes are the browser's business, and parsing them here would only add a
    version dependency. Type and size are checked, and nothing else.
    """
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object.")
    if len(json.dumps(value)) > MAX_SIGNAL_BYTES:
        raise ValidationError(f"{field} is too large.")
    return value


def _peer_id(db: Session, *, conversation_id: int, user_id: int) -> int:
    """The other person in a one-to-one conversation.

    Membership is re-checked on every single frame, not just on the invite.
    Without that, anyone who learned a conversation id could inject candidates
    into a call between two other people, or hang it up.
    """
    conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=user_id
    )
    conversation = conversation_service.get_conversation(db, conversation_id)

    if conversation.type is not ConversationType.DIRECT:
        # A group call means either a mesh of N*(N-1) peer connections or a
        # media server to mix the streams. Both are out of scope, and failing
        # clearly is better than half-connecting three people.
        raise ValidationError("Calls are only supported in one-to-one conversations.")

    others = [
        participant
        for participant in conversation_service.participant_ids(db, conversation_id)
        if participant != user_id
    ]
    if not others:
        raise ValidationError("There is nobody to call in this conversation.")
    return others[0]


def handle(db: Session, user: User, payload: dict[str, Any]) -> None:
    """Validate one signalling frame and forward it to the other party.

    Every branch ends in a publish to exactly one user, or an error raised back
    to the sender. Nothing is persisted.
    """
    event_type = payload.get("type")
    conversation_id = payload.get("conversation_id")

    if not isinstance(conversation_id, int):
        raise ValidationError("A call event needs a conversation_id.")

    peer_id = _peer_id(db, conversation_id=conversation_id, user_id=user.id)
    caller = UserPublic.model_validate(user).model_dump(mode="json")

    if event_type == CLIENT_INVITE:
        call_type = payload.get("call_type")
        if call_type not in CALL_TYPES:
            raise ValidationError("call_type must be 'audio' or 'video'.")
        offer = _checked_blob(payload.get("sdp"), "sdp")

        # Answered here rather than left to ring out: the caller should see
        # "unavailable" immediately instead of waiting on a timeout for someone
        # whose device is not even connected.
        if not manager.is_online(peer_id):
            events.publish(
                [user.id],
                events.event(
                    events.CALL_UNAVAILABLE,
                    conversation_id=conversation_id,
                    reason="offline",
                ),
            )
            return

        events.publish(
            [peer_id],
            events.event(
                events.CALL_INCOMING,
                conversation_id=conversation_id,
                call_type=call_type,
                sdp=offer,
                caller=caller,
            ),
        )
        return

    if event_type == CLIENT_ACCEPT:
        events.publish(
            [peer_id],
            events.event(
                events.CALL_ACCEPTED,
                conversation_id=conversation_id,
                sdp=_checked_blob(payload.get("sdp"), "sdp"),
                callee=caller,
            ),
        )
        return

    if event_type == CLIENT_CANDIDATE:
        # Candidates keep arriving after the call connects, as better network
        # paths are discovered, so this stays valid for the life of the call.
        events.publish(
            [peer_id],
            events.event(
                events.CALL_CANDIDATE,
                conversation_id=conversation_id,
                candidate=_checked_blob(payload.get("candidate"), "candidate"),
                from_user_id=user.id,
            ),
        )
        return

    if event_type in (CLIENT_DECLINE, CLIENT_HANGUP):
        # One event for both, with a reason. To the other end the distinction
        # is only a label -- either way the call is over and the peer
        # connection has to be torn down.
        events.publish(
            [peer_id],
            events.event(
                events.CALL_ENDED,
                conversation_id=conversation_id,
                reason="declined" if event_type == CLIENT_DECLINE else "hangup",
                from_user_id=user.id,
            ),
        )
        return

    raise ValidationError(f"Unknown call event: {event_type!r}")
