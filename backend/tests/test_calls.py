"""Call signalling: what the relay forwards, and what it refuses.

There is no media here and nothing to assert about audio or video -- that is
entirely the browser's business. What the server owns is who may signal whom,
and these tests are about exactly that.
"""

import pytest
from sqlalchemy.orm import Session

from app.services import conversation_service, group_service
from app.websocket import calls
from tests.conftest import await_event as _await_event
from tests.conftest import drain_ready as _drain_ready

# Stand-ins for what a browser would send. The server never parses these, so
# their contents are irrelevant beyond being JSON objects.
OFFER = {"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n"}
ANSWER = {"type": "answer", "sdp": "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n"}
CANDIDATE = {"candidate": "candidate:1 1 UDP 1 10.0.0.1 5000 typ host", "sdpMLineIndex": 0}


@pytest.fixture
def pair(db_session: Session, alice, bob):
    """A direct conversation between alice and bob."""
    return conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )


def test_an_invite_rings_the_other_participant(live, alice, bob, token_for, pair):
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as callee:
        _drain_ready(callee)
        with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
            _drain_ready(caller)
            caller.send_json({
                "type": "call.invite",
                "conversation_id": pair.id,
                "call_type": "video",
                "sdp": OFFER,
            })

            frame = _await_event(callee, "call.incoming")
            assert frame["data"]["call_type"] == "video"
            assert frame["data"]["sdp"] == OFFER
            assert frame["data"]["caller"]["username"] == "alice"
            assert frame["data"]["conversation_id"] == pair.id


def test_calling_someone_with_no_connection_reports_unavailable(live, alice, bob, token_for, pair):
    """Answered immediately rather than left to ring out.

    Bob has no socket at all here, so there is nothing to ring; making the
    caller wait for a timeout would be worse than saying so at once.
    """
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json({
            "type": "call.invite",
            "conversation_id": pair.id,
            "call_type": "audio",
            "sdp": OFFER,
        })

        frame = _await_event(caller, "call.unavailable")
        assert frame["data"]["reason"] == "offline"


def test_the_answer_reaches_the_caller(live, alice, bob, token_for, pair):
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        with live.websocket_connect(f"/ws?token={token_for(bob)}") as callee:
            _drain_ready(callee)
            callee.send_json({"type": "call.accept", "conversation_id": pair.id, "sdp": ANSWER})

            frame = _await_event(caller, "call.accepted")
            assert frame["data"]["sdp"] == ANSWER
            assert frame["data"]["callee"]["username"] == "bob"


def test_candidates_are_relayed_untouched(live, alice, bob, token_for, pair):
    """The server does not parse candidates; it moves them."""
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as callee:
        _drain_ready(callee)
        with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
            _drain_ready(caller)
            caller.send_json({
                "type": "call.candidate",
                "conversation_id": pair.id,
                "candidate": CANDIDATE,
            })

            frame = _await_event(callee, "call.candidate")
            assert frame["data"]["candidate"] == CANDIDATE
            assert frame["data"]["from_user_id"] == alice.id


@pytest.mark.parametrize(
    "event_type,reason",
    [("call.decline", "declined"), ("call.hangup", "hangup")],
)
def test_declining_and_hanging_up_both_end_the_call(
    live, alice, bob, token_for, pair, event_type: str, reason: str
):
    """One event, two labels.

    To the other end the distinction is only a label: either way the peer
    connection has to come down, so the client has one path to handle.
    """
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        with live.websocket_connect(f"/ws?token={token_for(bob)}") as callee:
            _drain_ready(callee)
            callee.send_json({"type": event_type, "conversation_id": pair.id})

            frame = _await_event(caller, "call.ended")
            assert frame["data"]["reason"] == reason
            assert frame["data"]["from_user_id"] == bob.id


def test_an_outsider_cannot_signal_into_a_conversation(live, alice, bob, carol, token_for, pair):
    """Membership is re-checked on every frame, not just on the invite.

    Without that, anyone who learned a conversation id could inject candidates
    into someone else's call, or hang it up.
    """
    with live.websocket_connect(f"/ws?token={token_for(carol)}") as intruder:
        _drain_ready(intruder)
        intruder.send_json({
            "type": "call.candidate",
            "conversation_id": pair.id,
            "candidate": CANDIDATE,
        })
        assert intruder.receive_json()["type"] == "error"


def test_a_group_conversation_refuses_calls(live, alice, bob, carol, token_for, db_session):
    """Failing clearly beats half-connecting three people.

    A group call needs either a mesh of peer connections or a media server;
    both are out of scope, so the server says so instead of relaying an offer
    to one arbitrary member.
    """
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id, carol.id]
    )
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json({
            "type": "call.invite",
            "conversation_id": group.id,
            "call_type": "audio",
            "sdp": OFFER,
        })

        frame = _await_event(caller, "error")
        assert "one-to-one" in frame["data"]["detail"]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"conversation_id": None}, id="no conversation"),
        pytest.param({"call_type": "hologram"}, id="unknown call type"),
        pytest.param({"call_type": None}, id="call type missing"),
        pytest.param({"sdp": "not-an-object"}, id="sdp not an object"),
        pytest.param({"sdp": None}, id="sdp missing"),
    ],
)
def test_malformed_invites_are_refused(live, alice, token_for, pair, overrides: dict):
    """A key set to None in the overrides is dropped from the frame entirely."""
    invite = {
        "type": "call.invite",
        "conversation_id": pair.id,
        "call_type": "video",
        "sdp": OFFER,
        **overrides,
    }
    invite = {key: value for key, value in invite.items() if value is not None}

    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json(invite)
        assert caller.receive_json()["type"] == "error"


def test_an_oversized_offer_is_refused(live, alice, bob, token_for, pair):
    """The signalling channel is not a general-purpose relay between accounts."""
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json({
            "type": "call.invite",
            "conversation_id": pair.id,
            "call_type": "audio",
            "sdp": {"type": "offer", "sdp": "x" * (calls.MAX_SIGNAL_BYTES + 1)},
        })
        assert caller.receive_json()["type"] == "error"


def test_a_bad_call_frame_does_not_close_the_socket(live, alice, token_for, pair):
    """One malformed event is not a broken session."""
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json({"type": "call.invite", "conversation_id": pair.id})
        assert caller.receive_json()["type"] == "error"

        caller.send_json({"type": "ping"})
        assert caller.receive_json()["type"] == "pong"
