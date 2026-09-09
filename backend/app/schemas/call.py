"""Schemas for call-support endpoints.

Not call *signalling* -- that stays on the websocket (see
app/websocket/calls.py). This is the one REST piece a call needs: the ICE
server list a browser's RTCPeerConnection is configured with.
"""

from pydantic import BaseModel


class IceServer(BaseModel):
    """One entry of the shape RTCPeerConnection expects verbatim.

    Field names match the browser's RTCIceServer dictionary exactly (`urls`,
    `username`, `credential`) so the frontend can pass entries straight
    through with no renaming.
    """

    urls: str | list[str]
    username: str | None = None
    credential: str | None = None


class IceServersResponse(BaseModel):
    ice_servers: list[IceServer]
