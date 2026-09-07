"""The live-connection registry.

One process, one registry, held in memory. That is a deliberate ceiling: a
second worker process would not see the first one's connections, and scaling
out needs a shared broker (Redis pub/sub) in front of this class. The interface
-- ``send_to_users`` -- is the seam where that would slot in, so nothing above
this module would change.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks which sockets belong to which user and fans events out to them.

    Registry bookkeeping is synchronous and unlocked. Every caller runs on the
    single event loop that owns the sockets, so there is no concurrent mutation
    to guard against -- and, more importantly, a disconnecting handler must be
    able to deregister itself *without awaiting*: a socket teardown can run
    while its task is being cancelled, where any await raises immediately and
    the cleanup would silently never happen.
    """

    def __init__(self) -> None:
        # A user may be connected several times over -- two tabs, a phone --
        # and every one of them must receive the same events.
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: int, websocket: WebSocket) -> bool:
        """Register an accepted socket. True if this is the user's first one.

        The return value is what presence hangs off: only the first connection
        makes a user "online", so opening a second tab is not an event.
        """
        first = not self._connections[user_id]
        self._connections[user_id].add(websocket)
        return first

    def disconnect(self, user_id: int, websocket: WebSocket) -> bool:
        """Deregister a socket. True if it was the user's last one."""
        sockets = self._connections.get(user_id)
        if sockets is None:
            return False
        sockets.discard(websocket)
        if sockets:
            return False
        del self._connections[user_id]
        return True

    def is_online(self, user_id: int) -> bool:
        """Whether this process currently holds a socket for the user."""
        return bool(self._connections.get(user_id))

    def online_users(self) -> set[int]:
        """Every user with a live connection here."""
        return set(self._connections)

    async def send_to_users(
        self, user_ids: list[int] | set[int], payload: dict[str, Any]
    ) -> None:
        """Deliver one event to every connection of every listed user.

        The target list is snapshotted before the first await, so a socket that
        closes mid-delivery cannot mutate the set being iterated. Sends are
        gathered rather than sequenced, so one slow client cannot hold up
        delivery to the rest; a send that raises means the peer is gone, and
        its socket is dropped rather than allowed to accumulate.
        """
        targets = [
            (user_id, socket)
            for user_id in set(user_ids)
            for socket in tuple(self._connections.get(user_id, ()))
        ]
        if not targets:
            return

        results = await asyncio.gather(
            *(socket.send_json(payload) for _, socket in targets),
            return_exceptions=True,
        )
        for (user_id, socket), result in zip(targets, results):
            if isinstance(result, Exception):
                logger.debug("Dropping dead socket for user %s", user_id)
                self.disconnect(user_id, socket)


# The single registry for the process. Imported directly rather than injected:
# it holds live sockets, so a second instance would silently deliver to nobody.
manager = ConnectionManager()
