"""ICE server credentials for calls.

Not call signalling (see app/websocket/calls.py) -- this is the one REST
piece a call needs before it can even try to connect: what STUN/TURN
servers to hand RTCPeerConnection.

STUN alone (Google's public servers) is enough on most home and office
networks. It is not enough behind symmetric NAT or a strict corporate/
carrier firewall, where the media needs relaying through a TURN server --
that gap is common enough ("Could not connect. One of you may be on a
network that blocks direct calls.") that a real TURN relay, not a decorative
one, is required. Metered.ca's TURN credentials API is that relay: short-
lived, dynamically-generated credentials rather than a static shared secret,
fetched fresh on every request rather than cached, so a revoked or rotated
key takes effect on the very next call.

This never raises. A call that cannot reach the TURN provider should still
be attempted over STUN alone -- worse odds, not a broken call screen -- so
every failure mode here degrades to "STUN only" instead of an error.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Google's public STUN servers: free, no credentials, no account. Enough to
# discover a peer's own public address, which is most of what two ordinary
# home/office networks need to connect directly.
STUN_ONLY: list[dict] = [
    {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]},
]

METERED_TIMEOUT_SECONDS = 5.0


def get_ice_servers() -> list[dict]:
    """STUN servers, plus a fresh TURN allocation from Metered.ca if configured."""
    if not settings.metered_turn_domain or not settings.metered_turn_api_key:
        return STUN_ONLY

    url = f"https://{settings.metered_turn_domain}/api/v1/turn/credentials"
    try:
        response = httpx.get(
            url,
            params={"apiKey": settings.metered_turn_api_key},
            timeout=METERED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        servers = response.json()
        if not isinstance(servers, list) or not servers:
            raise ValueError("Metered returned no ICE servers.")
        return servers
    except Exception:
        # Logged, not raised: a dead or misconfigured TURN provider should
        # degrade the call's odds, not take down call setup entirely.
        logger.warning("Could not fetch TURN credentials from Metered.ca", exc_info=True)
        return STUN_ONLY
