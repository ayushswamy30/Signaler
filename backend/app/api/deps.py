"""Shared route dependencies.

The aliases at the bottom are what routes actually annotate with, so a handler
signature reads ``def route(db: DbSession, user: CurrentUser)`` instead of
repeating a ``Depends`` chain in every function.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError
from app.database.database import get_db
from app.models.user import User
from app.services import auth_service

# auto_error=False so a missing header reaches this module rather than being
# turned into a 403 by the security scheme: an anonymous request should get
# 401 with a WWW-Authenticate header, which is what tells a client to log in.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token from /api/auth/login")

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the bearer token on the request to a user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise UNAUTHENTICATED
    try:
        return auth_service.user_from_access_token(db, credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
