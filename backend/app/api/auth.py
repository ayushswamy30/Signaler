"""Authentication routes: register, login, refresh, logout."""

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.common import Message
from app.schemas.user import UserMe
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(session: auth_service.IssuedSession) -> TokenResponse:
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user=UserMe.model_validate(session.user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession, request: Request) -> TokenResponse:
    """Create an account and sign in immediately.

    Registration returns tokens rather than redirecting to the login form: the
    credentials were just proven, and a second round trip would only be a place
    to fail.
    """
    user = user_service.create_user(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        phone_number=payload.phone_number,
    )
    session = auth_service.issue_session(db, user, user_agent=request.headers.get("user-agent"))
    return _token_response(session)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenResponse:
    """Exchange username and password for an access and refresh token pair."""
    user = auth_service.authenticate(db, username=payload.username, password=payload.password)
    session = auth_service.issue_session(db, user, user_agent=request.headers.get("user-agent"))
    return _token_response(session)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DbSession, request: Request) -> TokenResponse:
    """Trade a refresh token for a new pair. The presented token is revoked."""
    session = auth_service.refresh_session(
        db,
        refresh_token=payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
    )
    return _token_response(session)


@router.post("/logout", response_model=Message)
def logout(payload: RefreshRequest, db: DbSession) -> Message:
    """End one session.

    Unauthenticated on purpose: a client whose access token has already expired
    must still be able to invalidate its refresh token, and the token itself is
    the only credential the operation needs.
    """
    auth_service.revoke_session(db, refresh_token=payload.refresh_token)
    return Message(detail="Signed out.")


@router.post("/logout-all", response_model=Message)
def logout_all(db: DbSession, current_user: CurrentUser) -> Message:
    """End every session for the signed-in user, including this one."""
    auth_service.revoke_all_sessions(db, current_user)
    return Message(detail="Signed out of all devices.")


@router.get("/me", response_model=UserMe)
def read_me(current_user: CurrentUser) -> UserMe:
    """The signed-in user. Also the cheapest way for a client to test a token."""
    return UserMe.model_validate(current_user)
