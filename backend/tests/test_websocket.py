"""Realtime behaviour over the /ws socket.

The ``live`` fixture in conftest runs the application lifespan, which is what
makes these meaningful: without it an HTTP request would run on a different
event loop from the socket and no broadcast would ever arrive.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.services import conversation_service, group_service, message_service
from app.websocket.manager import manager
from tests.conftest import await_event as _await_event
from tests.conftest import drain_ready as _drain_ready


def _eventually(predicate, *, timeout: float = 3.0) -> bool:
    """Poll until ``predicate`` holds, or give up.

    Socket teardown finishes on the application's own thread, so a state change
    it makes is not necessarily visible the instant the client-side ``with``
    block exits. Polling asserts the outcome without asserting a schedule.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_a_socket_without_a_token_is_closed(live: TestClient):
    with pytest.raises(Exception):
        with live.websocket_connect("/ws") as socket:
            socket.receive_json()


def test_a_socket_with_a_bad_token_is_closed(live: TestClient):
    with pytest.raises(Exception):
        with live.websocket_connect("/ws?token=nonsense") as socket:
            socket.receive_json()


def test_connecting_yields_a_ready_frame_naming_the_user(live, alice, token_for):
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as socket:
        ready = _drain_ready(socket)
        assert ready["data"]["user"]["username"] == "alice"
        assert alice.id in ready["data"]["online_user_ids"]


def test_connecting_marks_the_user_online(live, alice, token_for, db_session):
    def presence_is(expected: bool) -> bool:
        # rollback() ends the read transaction, so the next query sees what the
        # application committed on its own connection rather than a snapshot.
        db_session.rollback()
        db_session.refresh(alice)
        return alice.is_online is expected

    with live.websocket_connect(f"/ws?token={token_for(alice)}") as socket:
        _drain_ready(socket)
        assert _eventually(lambda: presence_is(True))

    assert _eventually(lambda: presence_is(False))
    assert alice.last_seen is not None


def test_ping_is_answered_with_pong(live, alice, token_for):
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as socket:
        _drain_ready(socket)
        socket.send_json({"type": "ping"})
        assert socket.receive_json()["type"] == "pong"


def test_an_unknown_event_gets_an_error_but_keeps_the_socket_open(live, alice, token_for):
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as socket:
        _drain_ready(socket)
        socket.send_json({"type": "nonsense"})
        assert socket.receive_json()["type"] == "error"

        socket.send_json({"type": "ping"})
        assert socket.receive_json()["type"] == "pong"


def test_a_sent_message_reaches_the_other_participant(
    live, sign_in, alice, bob, token_for, db_session
):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as socket:
        _drain_ready(socket)

        sign_in(alice).post(
            f"/api/conversations/{conversation.id}/messages", json={"content": "over the wire"}
        )

        frame = _await_event(socket, "message.new")
        assert frame["data"]["message"]["content"] == "over the wire"
        assert frame["data"]["message"]["sender"]["username"] == "alice"


def test_an_edit_is_broadcast(live, sign_in, alice, bob, token_for, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=alice.id, content="typo"
    )
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as socket:
        _drain_ready(socket)

        sign_in(alice).patch(f"/api/messages/{message.id}", json={"content": "fixed"})

        frame = _await_event(socket, "message.updated")
        assert frame["data"]["message"]["content"] == "fixed"


def test_a_deletion_is_broadcast(live, sign_in, alice, bob, token_for, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=alice.id, content="regret"
    )
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as socket:
        _drain_ready(socket)

        sign_in(alice).delete(f"/api/messages/{message.id}")

        frame = _await_event(socket, "message.deleted")
        assert frame["data"]["message_id"] == message.id


def test_typing_reaches_the_other_side_only(live, alice, bob, token_for, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as listener:
        _drain_ready(listener)
        with live.websocket_connect(f"/ws?token={token_for(alice)}") as typist:
            _drain_ready(typist)
            typist.send_json({"type": "typing.start", "conversation_id": conversation.id})

            frame = _await_event(listener, "typing.start")
            assert frame["data"]["user"]["username"] == "alice"

            # The typist is not told about their own typing; a ping proves the
            # socket is responsive rather than merely slow.
            typist.send_json({"type": "ping"})
            assert typist.receive_json()["type"] == "pong"


def test_typing_in_a_conversation_you_are_not_in_is_refused(live, alice, bob, carol, token_for, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    with live.websocket_connect(f"/ws?token={token_for(carol)}") as socket:
        _drain_ready(socket)
        socket.send_json({"type": "typing.start", "conversation_id": conversation.id})
        assert socket.receive_json()["type"] == "error"


def test_read_receipts_go_back_to_the_sender(live, alice, bob, token_for, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=alice.id, content="read me"
    )
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as sender:
        _drain_ready(sender)
        with live.websocket_connect(f"/ws?token={token_for(bob)}") as reader:
            _drain_ready(reader)

            # Connecting delivers the pending message, which is itself a receipt.
            delivered = _await_event(sender, "message.status")
            assert delivered["data"]["status"] == "delivered"

            reader.send_json({"type": "message.read", "conversation_id": conversation.id})

            read = _await_event(sender, "message.status")
            assert read["data"]["status"] == "read"
            assert read["data"]["message_ids"] == [message.id]


def test_presence_is_announced_to_people_you_share_a_conversation_with(
    live, alice, bob, token_for, db_session
):
    conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as watcher:
        _drain_ready(watcher)
        with live.websocket_connect(f"/ws?token={token_for(bob)}") as other:
            _drain_ready(other)
            frame = _await_event(watcher, "presence")
            assert frame["data"]["user_id"] == bob.id
            assert frame["data"]["is_online"] is True

        offline = _await_event(watcher, "presence")
        assert offline["data"]["is_online"] is False


def test_a_new_group_is_pushed_to_its_members(live, sign_in, alice, bob, token_for):
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as socket:
        _drain_ready(socket)

        sign_in(alice).post("/api/groups", json={"name": "Surprise", "member_ids": [bob.id]})

        frame = _await_event(socket, "conversation.created")
        assert frame["data"]["conversation"]["name"] == "Surprise"
        assert frame["data"]["conversation"]["my_role"] == "member"


def test_removal_tells_the_group_and_the_person_removed(
    live, sign_in, alice, bob, carol, token_for, db_session
):
    """The two audiences get different events, so both are checked.

    The group hears "this person left"; the person removed hears "this
    conversation is gone" -- they are no longer a participant, so the first
    event is not theirs to receive.
    """
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id, carol.id]
    )
    with live.websocket_connect(f"/ws?token={token_for(bob)}") as removed:
        _drain_ready(removed)
        with live.websocket_connect(f"/ws?token={token_for(carol)}") as remaining:
            _drain_ready(remaining)

            sign_in(alice).delete(f"/api/groups/{group.id}/members/{bob.id}")

            notice = _await_event(remaining, "group.member_removed")
            assert notice["data"]["user_id"] == bob.id

            gone = _await_event(removed, "conversation.deleted")
            assert gone["data"]["conversation_id"] == group.id


def test_a_second_connection_does_not_change_presence(live, alice, token_for, db_session):
    """Two tabs are one presence.

    Asserted on the registry rather than on frame ordering: "no event was sent"
    is not something a socket can report, and inferring it from what arrives
    next makes the test depend on scheduling.
    """
    with live.websocket_connect(f"/ws?token={token_for(alice)}") as first:
        _drain_ready(first)
        assert manager.is_online(alice.id)

        with live.websocket_connect(f"/ws?token={token_for(alice)}") as second:
            _drain_ready(second)
            assert len(manager._connections[alice.id]) == 2

        # One tab closed; the user is still here.
        assert _eventually(lambda: len(manager._connections.get(alice.id, ())) == 1)

        db_session.rollback()
        db_session.refresh(alice)
        assert alice.is_online is True
