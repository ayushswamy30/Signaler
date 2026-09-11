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


@pytest.fixture
def team(db_session: Session, alice, bob, carol):
    """A group conversation with alice, bob and carol in it."""
    return group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id, carol.id]
    )


def test_a_group_invite_rings_everyone_else(live, alice, bob, carol, token_for, team):
    """One invite, every other member. A group call is not a call to one person
    who happens to be in a group -- everyone's device has to ring, and each one
    that answers negotiates its own connection."""
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as first:
        _drain_ready(first)
        with live.websocket_connect(f"/ws?token={token_for(carol)}") as second:
            _drain_ready(second)
            with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
                _drain_ready(caller)
                caller.send_json({
                    "type": "call.invite",
                    "conversation_id": team.id,
                    "call_type": "video",
                })

                for ringing in (first, second):
                    frame = _await_event(ringing, "call.incoming")
                    assert frame["data"]["is_group"] is True
                    assert frame["data"]["call_type"] == "video"
                    assert frame["data"]["caller"]["username"] == "alice"
                    # No offer: there is a different one for every pair, and
                    # neither exists until somebody answers.
                    assert "sdp" not in frame["data"]


def test_joining_a_group_call_is_announced_to_everyone(live, alice, bob, carol, token_for, team):
    """The server holds no call state, so "who is in this call" is something
    the members tell each other. An accept therefore reaches the whole
    conversation, not just whoever placed the call."""
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        with live.websocket_connect(f"/ws?token={token_for(carol)}") as third:
            _drain_ready(third)
            with live.websocket_connect(f"/ws?token={token_for(bob)}") as joiner:
                _drain_ready(joiner)
                joiner.send_json({"type": "call.accept", "conversation_id": team.id})

                for listener in (caller, third):
                    frame = _await_event(listener, "call.joined")
                    assert frame["data"]["participant"]["username"] == "bob"
                    assert frame["data"]["conversation_id"] == team.id


def test_a_group_offer_goes_only_to_the_peer_it_names(live, alice, bob, carol, token_for, team):
    """A mesh negotiates pair by pair, so these frames are addressed. Carol is
    in the same call and must not receive bob's offer -- hers is different."""
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as target:
        _drain_ready(target)
        with live.websocket_connect(f"/ws?token={token_for(carol)}") as bystander:
            _drain_ready(bystander)
            with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
                _drain_ready(caller)
                caller.send_json({
                    "type": "call.offer",
                    "conversation_id": team.id,
                    "target_user_id": bob.id,
                    "call_type": "audio",
                    "sdp": OFFER,
                })
                frame = _await_event(target, "call.peer_offer")
                assert frame["data"]["sdp"] == OFFER
                assert frame["data"]["peer"]["username"] == "alice"

                target.send_json({
                    "type": "call.answer",
                    "conversation_id": team.id,
                    "target_user_id": alice.id,
                    "sdp": ANSWER,
                })
                back = _await_event(caller, "call.peer_answer")
                assert back["data"]["sdp"] == ANSWER
                assert back["data"]["peer"]["username"] == "bob"

                # Carol saw neither. Anything she did receive would mean the
                # mesh was leaking one pair's negotiation into another.
                bystander.send_json({"type": "call.hangup", "conversation_id": team.id})
                assert _await_event(caller, "call.ended")["data"]["from_user_id"] == carol.id


def test_a_group_frame_must_name_a_real_participant(live, alice, bob, token_for, team, carol):
    """The target is checked against the membership list rather than trusted:
    otherwise a member could push candidates at any account they could name."""
    outsider = 99_999
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        for target in (outsider, None, alice.id):
            caller.send_json({
                "type": "call.candidate",
                "conversation_id": team.id,
                "target_user_id": target,
                "candidate": CANDIDATE,
            })
            frame = _await_event(caller, "error")
            assert "target_user_id" in frame["data"]["detail"]


def test_leaving_a_group_call_reaches_everyone(live, alice, bob, carol, token_for, team):
    """One person leaving a group call is not the call ending, but every other
    client still has a connection to that person to tear down."""
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as first:
        _drain_ready(first)
        with live.websocket_connect(f"/ws?token={token_for(carol)}") as second:
            _drain_ready(second)
            with live.websocket_connect(f"/ws?token={token_for(alice)}") as leaver:
                _drain_ready(leaver)
                leaver.send_json({"type": "call.hangup", "conversation_id": team.id})

                for remaining in (first, second):
                    frame = _await_event(remaining, "call.ended")
                    assert frame["data"]["reason"] == "hangup"
                    assert frame["data"]["from_user_id"] == alice.id


def test_a_one_to_one_conversation_refuses_mesh_frames(live, alice, bob, token_for, pair):
    """The per-pair frames exist because a mesh has more than one pair. In a
    one-to-one call the negotiation rides on the invite and the accept, so an
    offer arriving outside that would be answering nothing."""
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as caller:
        _drain_ready(caller)
        caller.send_json({
            "type": "call.offer",
            "conversation_id": pair.id,
            "target_user_id": bob.id,
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
