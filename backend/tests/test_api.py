"""HTTP behaviour: status codes, authorisation, and response shapes.

These go through the real application with a temporary database, so they cover
the wiring the service tests deliberately skip -- dependency injection, the
error-to-status mapping, and what the JSON actually looks like.
"""

import pytest
from fastapi.testclient import TestClient

from app.services import conversation_service, group_service, message_service
from tests.conftest import DEFAULT_PASSWORD

REGISTRATION = {
    "username": "newcomer",
    "password": "a-long-enough-password",
    "display_name": "New Comer",
}


# --------------------------------------------------------------------------
# Authentication endpoints
# --------------------------------------------------------------------------


def test_register_returns_tokens_and_the_new_user(client: TestClient):
    response = client.post("/api/auth/register", json=REGISTRATION)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "newcomer"
    assert "password" not in str(body["user"])


def test_registering_a_taken_username_is_a_conflict(client: TestClient, alice):
    response = client.post(
        "/api/auth/register", json={**REGISTRATION, "username": "alice"}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [
        ("username", "x"),           # too short
        ("username", "9lives"),      # must start with a letter
        ("username", "has spaces"),
        ("password", "short"),
        ("display_name", ""),
        ("phone_number", "not-a-number"),
    ],
)
def test_registration_rejects_malformed_input(client: TestClient, field: str, value: str):
    response = client.post("/api/auth/register", json={**REGISTRATION, field: value})
    assert response.status_code == 422


def test_username_is_normalised_to_lower_case(client: TestClient):
    client.post("/api/auth/register", json={**REGISTRATION, "username": "MixedCase"})
    response = client.post(
        "/api/auth/login", json={"username": "mixedcase", "password": REGISTRATION["password"]}
    )
    assert response.status_code == 200


def test_login_with_the_wrong_password_is_401(client: TestClient, alice):
    response = client.post(
        "/api/auth/login", json={"username": "alice", "password": "not-it-at-all"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_refresh_returns_a_new_pair_and_burns_the_old_one(client: TestClient, alice):
    login = client.post(
        "/api/auth/login", json={"username": "alice", "password": DEFAULT_PASSWORD}
    ).json()

    first = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert first.status_code == 200

    replay = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert replay.status_code == 401


def test_logout_revokes_the_session(client: TestClient, alice):
    login = client.post(
        "/api/auth/login", json={"username": "alice", "password": DEFAULT_PASSWORD}
    ).json()
    client.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]})

    response = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Authorisation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/users/me"),
        ("get", "/api/contacts"),
        ("get", "/api/conversations"),
        ("get", "/api/users/search?q=a"),
        ("post", "/api/groups"),
    ],
)
def test_protected_endpoints_reject_anonymous_requests(
    client: TestClient, method: str, path: str
):
    # GET takes no body, so the payload is only passed where a body is legal.
    kwargs = {"json": {}} if method == "post" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_a_garbage_token_is_rejected(client: TestClient):
    client.headers["Authorization"] = "Bearer not.a.token"
    assert client.get("/api/users/me").status_code == 401


def test_health_stays_public(client: TestClient):
    assert client.get("/api/health").status_code == 200


# --------------------------------------------------------------------------
# Users and contacts
# --------------------------------------------------------------------------


def test_me_returns_the_signed_in_user(authed, alice):
    body = authed(alice).get("/api/users/me").json()
    assert body["username"] == "alice"
    assert "password_hash" not in body


def test_profile_can_be_edited(authed, alice):
    body = authed(alice).patch("/api/users/me", json={"about": "  Testing  "}).json()
    assert body["about"] == "Testing"


def test_search_excludes_the_searcher(authed, alice, bob):
    results = authed(alice).get("/api/users/search", params={"q": "a"}).json()
    assert alice.id not in [user["id"] for user in results]


def test_search_path_is_not_swallowed_by_the_user_id_route(authed, alice, bob):
    """/users/search must not be parsed as /users/{user_id}."""
    assert authed(alice).get("/api/users/search", params={"q": "bob"}).status_code == 200


def test_contacts_round_trip(authed, alice, bob):
    client = authed(alice)
    assert client.post("/api/contacts", json={"user_id": bob.id}).status_code == 201
    assert [c["contact_user"]["id"] for c in client.get("/api/contacts").json()] == [bob.id]
    assert client.delete(f"/api/contacts/{bob.id}").status_code == 200
    assert client.get("/api/contacts").json() == []


def test_removing_a_contact_you_never_had_is_404(authed, alice, bob):
    assert authed(alice).delete(f"/api/contacts/{bob.id}").status_code == 404


def test_adding_yourself_as_a_contact_is_422(authed, alice):
    assert authed(alice).post("/api/contacts", json={"user_id": alice.id}).status_code == 422


# --------------------------------------------------------------------------
# Conversations and messages
# --------------------------------------------------------------------------


def test_opening_a_direct_conversation_is_idempotent(authed, alice, bob):
    client = authed(alice)
    first = client.post("/api/conversations/direct", json={"user_id": bob.id}).json()
    second = client.post("/api/conversations/direct", json={"user_id": bob.id}).json()
    assert first["id"] == second["id"]


def test_conversation_payload_carries_the_viewers_own_state(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="hello"
    )
    body = authed(alice).get(f"/api/conversations/{conversation.id}").json()

    assert body["unread_count"] == 1
    assert body["muted"] is False
    assert body["last_message"]["content"] == "hello"
    assert len(body["participants"]) == 2


def test_a_conversation_you_are_not_in_is_404(authed, carol, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    assert authed(carol).get(f"/api/conversations/{conversation.id}").status_code == 404


def test_send_and_read_back_a_message(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    client = authed(alice)
    sent = client.post(
        f"/api/conversations/{conversation.id}/messages", json={"content": "hello there"}
    )
    assert sent.status_code == 201
    assert sent.json()["status"] == "sent"

    history = client.get(f"/api/conversations/{conversation.id}/messages").json()
    assert [m["content"] for m in history["messages"]] == ["hello there"]
    assert history["next_before_id"] is None


def test_history_paginates(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    for n in range(5):
        message_service.send_message(
            db_session, conversation_id=conversation.id, sender_id=alice.id, content=str(n)
        )

    client = authed(alice)
    page = client.get(
        f"/api/conversations/{conversation.id}/messages", params={"limit": 2}
    ).json()
    assert [m["content"] for m in page["messages"]] == ["3", "4"]

    older = client.get(
        f"/api/conversations/{conversation.id}/messages",
        params={"limit": 2, "before_id": page["next_before_id"]},
    ).json()
    assert [m["content"] for m in older["messages"]] == ["1", "2"]


def test_a_reply_carries_a_quoted_preview(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    original = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="the question"
    )
    body = authed(alice).post(
        f"/api/conversations/{conversation.id}/messages",
        json={"content": "the answer", "reply_to_id": original.id},
    ).json()

    assert body["reply_to"]["content"] == "the question"
    assert body["reply_to"]["sender_display_name"] == bob.display_name


def test_editing_someone_elses_message_is_403(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="theirs"
    )
    response = authed(alice).patch(f"/api/messages/{message.id}", json={"content": "mine now"})
    assert response.status_code == 403


def test_marking_read_clears_the_unread_count(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="hello"
    )
    client = authed(alice)
    client.post(f"/api/conversations/{conversation.id}/read", json={})

    body = client.get(f"/api/conversations/{conversation.id}").json()
    assert body["unread_count"] == 0


def test_muting_is_reflected_in_the_payload(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    body = authed(alice).patch(
        f"/api/conversations/{conversation.id}/mute", json={"muted": True}
    ).json()
    assert body["muted"] is True


# --------------------------------------------------------------------------
# Groups
# --------------------------------------------------------------------------


def test_create_a_group(authed, alice, bob, carol):
    body = authed(alice).post(
        "/api/groups", json={"name": "Weekend", "member_ids": [bob.id, carol.id]}
    ).json()

    assert body["type"] == "group"
    assert body["my_role"] == "admin"
    assert len(body["participants"]) == 3


def test_a_group_needs_at_least_one_other_member(authed, alice):
    response = authed(alice).post("/api/groups", json={"name": "Alone", "member_ids": []})
    assert response.status_code == 422


def test_only_admins_may_rename(authed, alice, bob, db_session):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    response = authed(bob).patch(f"/api/groups/{group.id}", json={"name": "Hijacked"})
    assert response.status_code == 403


def test_add_and_remove_members(authed, alice, bob, carol, db_session):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    client = authed(alice)

    added = client.post(f"/api/groups/{group.id}/members", json={"member_ids": [carol.id]})
    assert added.status_code == 201
    assert [p["user"]["id"] for p in added.json()] == [carol.id]

    assert client.delete(f"/api/groups/{group.id}/members/{carol.id}").status_code == 200
    members = client.get(f"/api/conversations/{group.id}/members").json()
    assert carol.id not in [m["user"]["id"] for m in members]


def test_promote_a_member(authed, alice, bob, db_session):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    body = authed(alice).patch(
        f"/api/groups/{group.id}/members/{bob.id}", json={"role": "admin"}
    ).json()
    assert body["role"] == "admin"


def test_leaving_removes_the_group_from_your_list(authed, alice, bob, db_session):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    client = authed(bob)
    assert client.post(f"/api/groups/{group.id}/leave").status_code == 200
    assert client.get(f"/api/conversations/{group.id}").status_code == 404


def test_group_routes_refuse_a_direct_conversation(authed, alice, bob, db_session):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    response = authed(alice).patch(f"/api/groups/{conversation.id}", json={"name": "Nope"})
    assert response.status_code == 422


# --------------------------------------------------------------------------
# The OpenAPI contract
# --------------------------------------------------------------------------


def test_openapi_document_is_generated(client: TestClient):
    """A broken response model shows up here before it shows up in a client."""
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/conversations" in schema.json()["paths"]


def test_the_socket_is_not_in_the_openapi_document(client: TestClient):
    """It is not an HTTP endpoint; listing it would mislead a generated client."""
    assert "/ws" not in client.get("/openapi.json").json()["paths"]


def test_password_hash_never_appears_in_any_response_schema(client: TestClient):
    schema = client.get("/openapi.json").json()
    assert "password_hash" not in str(schema["components"]["schemas"])
