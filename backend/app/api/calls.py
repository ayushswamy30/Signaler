"""Call-support routes.

Signalling (offer/answer/candidates) happens over the websocket -- see
app/websocket/calls.py. The one thing a call needs over plain REST is the
ICE server list, fetched fresh right before a call is placed or answered
rather than baked into the client bundle, so a TURN credential rotation or
provider swap takes effect without a redeploy.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.call import IceServersResponse
from app.services import call_service

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/ice-servers", response_model=IceServersResponse, response_model_exclude_none=True)
def read_ice_servers(current_user: CurrentUser) -> IceServersResponse:
    """STUN and (if configured) TURN servers for RTCPeerConnection.

    Authenticated only to keep a free-tier TURN quota from being drained by
    anyone who finds the URL -- the credentials themselves are still
    short-lived and safe to hand to any signed-in client.
    """
    return IceServersResponse(ice_servers=call_service.get_ice_servers())
