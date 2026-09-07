"""End-to-end smoke test against a real running server.

Different in kind from the pytest suite, which drives the ASGI application
in-process with a test client. This starts uvicorn as its own process on a
throwaway database and talks to it over real HTTP and a real WebSocket, so it
exercises the parts the suite cannot: the socket handshake, the ASGI server, the
lifespan that binds the event loop, and CORS.

    python -m scripts.smoke_e2e

Exits non-zero on the first failed check, so it is usable as a deployment gate.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import websockets

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 8123
BASE = f"http://{HOST}:{PORT}"
WS_BASE = f"ws://{HOST}:{PORT}"

PASSWORD = "smoke-test-password"

# Fail rather than hang: a socket that never delivers an expected event is a
# bug, and a test that waits forever reports nothing.
EVENT_TIMEOUT = 10.0

passed = 0


def check(condition: bool, description: str) -> None:
    """Assert one behaviour, and say so either way."""
    global passed
    if condition:
        passed += 1
        print(f"  ok   {description}")
    else:
        print(f"  FAIL {description}")
        raise SystemExit(f"Smoke test failed: {description}")


def start_server(database_url: str) -> subprocess.Popen[bytes]:
    """Launch uvicorn on a temporary database and wait for it to answer."""
    environment = {
        **os.environ,
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "development",
        "JWT_SECRET_KEY": "smoke-test-secret",
        # The lowest bcrypt cost: this test registers several accounts and the
        # work factor would otherwise dominate its runtime.
        "BCRYPT_ROUNDS": "4",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=BACKEND_DIR,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit("The server exited during startup.")
        try:
            if httpx.get(f"{BASE}/api/health", timeout=1).status_code == 200:
                return process
        except httpx.HTTPError:
            time.sleep(0.2)
    process.terminate()
    raise SystemExit("The server did not become healthy within 30 seconds.")


async def next_event(socket: Any, wanted: str) -> dict[str, Any]:
    """Read frames until the named event arrives, or time out."""
    async def read_until() -> dict[str, Any]:
        while True:
            frame = json.loads(await socket.recv())
            if frame.get("type") == wanted:
                return frame

    return await asyncio.wait_for(read_until(), timeout=EVENT_TIMEOUT)


async def run() -> None:
    stamp = str(int(time.time()))
    alice_name, bob_name, carol_name = (f"alice{stamp}", f"bob{stamp}", f"carol{stamp}")

    async with httpx.AsyncClient(base_url=BASE, timeout=10) as http:
        print("\nRegistration and sign-in")
        accounts = {}
        for username in (alice_name, bob_name, carol_name):
            response = await http.post(
                "/api/auth/register",
                json={
                    "username": username,
                    "password": PASSWORD,
                    "display_name": username.title(),
                },
            )
            check(response.status_code == 201, f"registered {username}")
            accounts[username] = response.json()

        alice, bob, carol = (accounts[name] for name in (alice_name, bob_name, carol_name))
        alice_auth = {"Authorization": f"Bearer {alice['access_token']}"}
        bob_auth = {"Authorization": f"Bearer {bob['access_token']}"}

        duplicate = await http.post(
            "/api/auth/register",
            json={"username": alice_name, "password": PASSWORD, "display_name": "Impostor"},
        )
        check(duplicate.status_code == 409, "a duplicate username is rejected")

        wrong = await http.post(
            "/api/auth/login", json={"username": alice_name, "password": "not-the-password"}
        )
        check(wrong.status_code == 401, "a wrong password is rejected")

        anonymous = await http.get("/api/conversations")
        check(anonymous.status_code == 401, "an unauthenticated request is rejected")

        print("\nContacts and search")
        found = await http.get("/api/users/search", params={"q": bob_name}, headers=alice_auth)
        check(
            any(user["id"] == bob["user"]["id"] for user in found.json()),
            "search finds another user by username",
        )
        added = await http.post(
            "/api/contacts", json={"user_id": bob["user"]["id"]}, headers=alice_auth
        )
        check(added.status_code == 201, "a contact is saved")

        print("\nDirect messaging over a live socket")
        conversation = (
            await http.post(
                "/api/conversations/direct",
                json={"user_id": bob["user"]["id"]},
                headers=alice_auth,
            )
        ).json()
        check(conversation["type"] == "direct", "a direct conversation is opened")

        async with websockets.connect(f"{WS_BASE}/ws?token={bob['access_token']}") as bob_socket:
            ready = await next_event(bob_socket, "ready")
            check(ready["data"]["user"]["username"] == bob_name, "the socket authenticates")

            sent = await http.post(
                f"/api/conversations/{conversation['id']}/messages",
                json={"content": "hello over a real socket"},
                headers=alice_auth,
            )
            check(sent.status_code == 201, "a message is accepted")

            delivered = await next_event(bob_socket, "message.new")
            check(
                delivered["data"]["message"]["content"] == "hello over a real socket",
                "the message arrives on the recipient's socket",
            )

            message_id = sent.json()["id"]
            await http.patch(
                f"/api/messages/{message_id}",
                json={"content": "edited over a real socket"},
                headers=alice_auth,
            )
            edited = await next_event(bob_socket, "message.updated")
            check(
                edited["data"]["message"]["content"] == "edited over a real socket",
                "an edit is broadcast",
            )

            async with websockets.connect(
                f"{WS_BASE}/ws?token={alice['access_token']}"
            ) as alice_socket:
                await next_event(alice_socket, "ready")

                await bob_socket.send(
                    json.dumps(
                        {"type": "typing.start", "conversation_id": conversation["id"]}
                    )
                )
                typing = await next_event(alice_socket, "typing.start")
                check(typing["data"]["user"]["username"] == bob_name, "typing is relayed")

                await bob_socket.send(
                    json.dumps({"type": "message.read", "conversation_id": conversation["id"]})
                )
                receipt = await next_event(alice_socket, "message.status")
                check(receipt["data"]["status"] == "read", "a read receipt reaches the sender")

            await http.delete(f"/api/messages/{message_id}", headers=alice_auth)
            removed = await next_event(bob_socket, "message.deleted")
            check(removed["data"]["message_id"] == message_id, "a deletion is broadcast")

        print("\nGroups")
        async with websockets.connect(f"{WS_BASE}/ws?token={carol['access_token']}") as carol_socket:
            await next_event(carol_socket, "ready")

            group = (
                await http.post(
                    "/api/groups",
                    json={
                        "name": "Smoke Test Group",
                        "member_ids": [bob["user"]["id"], carol["user"]["id"]],
                    },
                    headers=alice_auth,
                )
            ).json()
            check(group["my_role"] == "admin", "the creator is the group admin")

            pushed = await next_event(carol_socket, "conversation.created")
            check(
                pushed["data"]["conversation"]["name"] == "Smoke Test Group",
                "a new group is pushed to its members",
            )

            forbidden = await http.patch(
                f"/api/groups/{group['id']}", json={"name": "Hijacked"}, headers=bob_auth
            )
            check(forbidden.status_code == 403, "a member cannot rename the group")

            renamed = await http.patch(
                f"/api/groups/{group['id']}", json={"name": "Renamed Group"}, headers=alice_auth
            )
            check(renamed.json()["name"] == "Renamed Group", "an admin can rename the group")

            await http.delete(
                f"/api/groups/{group['id']}/members/{carol['user']['id']}", headers=alice_auth
            )
            gone = await next_event(carol_socket, "conversation.deleted")
            check(
                gone["data"]["conversation_id"] == group["id"],
                "a removed member is told the conversation is gone",
            )

        print("\nSessions")
        refreshed = await http.post(
            "/api/auth/refresh", json={"refresh_token": alice["refresh_token"]}
        )
        check(refreshed.status_code == 200, "a refresh token is exchanged")
        replay = await http.post(
            "/api/auth/refresh", json={"refresh_token": alice["refresh_token"]}
        )
        check(replay.status_code == 401, "a used refresh token cannot be replayed")

        new_refresh = refreshed.json()["refresh_token"]
        await http.post("/api/auth/logout", json={"refresh_token": new_refresh})
        after_logout = await http.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        check(after_logout.status_code == 401, "logout ends the session")

        print("\nConversation list")
        listed = (await http.get("/api/conversations", headers=bob_auth)).json()
        check(len(listed) == 2, "the conversation list holds the direct chat and the group")
        check(
            all("unread_count" in row and "my_role" in row for row in listed),
            "each row carries the viewer's own state",
        )


def main() -> None:
    workspace = tempfile.mkdtemp(prefix="signaler-smoke-")
    database = Path(workspace) / "smoke.db"
    database_url = f"sqlite:///{database.as_posix()}"

    print(f"Migrating a throwaway database at {database}")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
        stdout=subprocess.DEVNULL,
    )

    print(f"Starting the server on {BASE}")
    server = start_server(database_url)
    try:
        asyncio.run(run())
        print(f"\nAll {passed} checks passed.")
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
