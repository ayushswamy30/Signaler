"""Call signalling: the relay that lets browsers negotiate a call between them.

The server carries no audio or video. WebRTC peers exchange a session
description and a list of network candidates, and once they agree the media
flows between the devices directly -- so this module only forwards small JSON
blobs between people who already share a conversation, and forgets them
immediately.

A one-to-one call is one peer connection. A group call is a *mesh*: every pair
of participants negotiates its own connection, so a call of N people is
N*(N-1)/2 connections and each person uploads their camera N-1 times. That is
why the mesh is the right shape here and a media server is not: these are small
group chats, the server is free-tier, and an SFU would have to receive and
re-encode every stream. It also means the group frames are *addressed* --
`target_user_id` says which peer an offer, answer or candidate belongs to --
while ringing and leaving are fanned out to everybody.

No call state is stored. A ringing table held in memory would be lost on every
restart and would be wrong the moment a second worker existed, so "is the other
person reachable" is answered from live socket presence, "who is in the call"
is answered by the clients announcing themselves to each other, and "am I
already on a call" is answered by the client, which is the only party that
actually knows.
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
# Group only: the per-pair negotiation that a one-to-one call folds into its
# invite and accept. In a mesh the invite rings everybody at once and carries
# no offer, because each pair needs a different one.
CLIENT_OFFER = "call.offer"
CLIENT_ANSWER = "call.answer"

CLIENT_EVENTS = frozenset(
    {
        CLIENT_INVITE,
        CLIENT_ACCEPT,
        CLIENT_DECLINE,
        CLIENT_HANGUP,
        CLIENT_CANDIDATE,
        CLIENT_OFFER,
        CLIENT_ANSWER,
    }
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


def _others(
    db: Session, *, conversation_id: int, user_id: int
) -> tuple[ConversationType, list[int]]:
    """Everyone in the conversation except the sender.

    Membership is re-checked on every single frame, not just on the invite.
    Without that, anyone who learned a conversation id could inject candidates
    into a call between other people, or hang it up.
    """
    conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=user_id
    )
    conversation = conversation_service.get_conversation(db, conversation_id)

    others = [
        participant
        for participant in conversation_service.participant_ids(db, conversation_id)
        if participant != user_id
    ]
    if not others:
        raise ValidationError("There is nobody to call in this conversation.")
    return conversation.type, others


def handle(db: Session, user: User, payload: dict[str, Any]) -> None:
    """Validate one signalling frame and forward it to whoever it is for.

    Every branch ends in a publish to a checked set of participants, or an
    error raised back to the sender. Nothing is persisted.
    """
    event_type = payload.get("type")
    conversation_id = payload.get("conversation_id")

    if not isinstance(conversation_id, int):
        raise ValidationError("A call event needs a conversation_id.")

    conversation_type, others = _others(
        db, conversation_id=conversation_id, user_id=user.id
    )
    is_group = conversation_type is not ConversationType.DIRECT
    sender = UserPublic.model_validate(user).model_dump(mode="json")

    def addressed() -> list[int]:
        """The single peer a negotiation frame is meant for.

        One-to-one has only one candidate for that and says nothing; a mesh
        has to name the peer, and the name is checked against the membership
        list rather than trusted.
        """
        if not is_group:
            return others[:1]
        target = payload.get("target_user_id")
        if not isinstance(target, int) or target not in others:
            raise ValidationError("target_user_id must name another participant.")
        return [target]

    if event_type == CLIENT_INVITE:
        call_type = payload.get("call_type")
        if call_type not in CALL_TYPES:
            raise ValidationError("call_type must be 'audio' or 'video'.")

        # A group invite carries no offer: each ringing device will negotiate
        # its own connection with each person who answers, so there is nothing
        # useful to put here that would be the same for all of them.
        #
        # Validated before presence is consulted, so a malformed frame is
        # refused as malformed rather than being reported back as "nobody is
        # online" -- which would be a lie, and an unfixable one to debug.
        extra: dict[str, Any] = (
            {} if is_group else {"sdp": _checked_blob(payload.get("sdp"), "sdp")}
        )

        # Answered here rather than left to ring out: the caller should see
        # "unavailable" immediately instead of waiting on a timeout for people
        # whose devices are not even connected.
        reachable = [peer for peer in others if manager.is_online(peer)]
        if not reachable:
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
            reachable,
            events.event(
                events.CALL_INCOMING,
                conversation_id=conversation_id,
                call_type=call_type,
                is_group=is_group,
                caller=sender,
                **extra,
            ),
        )
        return

    if event_type == CLIENT_ACCEPT:
        if is_group:
            # "I am in this call now." Fanned out to the whole conversation
            # rather than to the caller alone, because everyone already in the
            # call needs to open a connection to the new arrival -- and the
            # server, holding no call state, does not know who that is.
            events.publish(
                others,
                events.event(
                    events.CALL_JOINED,
                    conversation_id=conversation_id,
                    participant=sender,
                ),
            )
            return

        events.publish(
            others[:1],
            events.event(
                events.CALL_ACCEPTED,
                conversation_id=conversation_id,
                sdp=_checked_blob(payload.get("sdp"), "sdp"),
                callee=sender,
            ),
        )
        return

    if event_type in (CLIENT_OFFER, CLIENT_ANSWER):
        if not is_group:
            # One-to-one negotiation rides on the invite and the accept; a
            # stray offer outside that would be answering nothing.
            raise ValidationError(
                "Use call.invite and call.accept in a one-to-one conversation."
            )
        is_offer = event_type == CLIENT_OFFER
        extra_offer: dict[str, Any] = {}
        if is_offer:
            # Carried so a device that is ringing, and has not chosen audio or
            # video yet, learns which one this call is before it answers.
            call_type = payload.get("call_type")
            if call_type not in CALL_TYPES:
                raise ValidationError("call_type must be 'audio' or 'video'.")
            extra_offer["call_type"] = call_type

        events.publish(
            addressed(),
            events.event(
                events.CALL_PEER_OFFER if is_offer else events.CALL_PEER_ANSWER,
                conversation_id=conversation_id,
                sdp=_checked_blob(payload.get("sdp"), "sdp"),
                peer=sender,
                **extra_offer,
            ),
        )
        return

    if event_type == CLIENT_CANDIDATE:
        # Candidates keep arriving after the call connects, as better network
        # paths are discovered, so this stays valid for the life of the call.
        events.publish(
            addressed(),
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
        # is only a label -- either way this person is out and their peer
        # connection has to be torn down. In a group that is one connection of
        # several, so it goes to everyone and each client drops just that peer.
        events.publish(
            others,
            events.event(
                events.CALL_ENDED,
                conversation_id=conversation_id,
                reason="declined" if event_type == CLIENT_DECLINE else "hangup",
                from_user_id=user.id,
            ),
        )
        return

    raise ValidationError(f"Unknown call event: {event_type!r}")
