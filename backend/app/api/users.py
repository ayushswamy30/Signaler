"""User routes: the signed-in profile, search, and public profiles."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.schemas.user import PasswordChange, UserMe, UserPublic, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMe)
def read_profile(current_user: CurrentUser) -> UserMe:
    """The signed-in user's own profile, including their private fields."""
    return UserMe.model_validate(current_user)


@router.patch("/me", response_model=UserMe)
def update_profile(payload: UserUpdate, db: DbSession, current_user: CurrentUser) -> UserMe:
    """Edit display name, about line, or avatar."""
    user = user_service.update_profile(
        db,
        current_user,
        display_name=payload.display_name,
        about=payload.about,
        avatar_url=payload.avatar_url,
    )
    return UserMe.model_validate(user)


@router.post("/me/password", response_model=Message)
def change_password(payload: PasswordChange, db: DbSession, current_user: CurrentUser) -> Message:
    """Change the password, which signs every session out."""
    user_service.change_password(
        db,
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return Message(detail="Password changed. Sign in again on your other devices.")


@router.get("/search", response_model=list[UserPublic])
def search(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(default="", max_length=100, description="Username, display name, or phone"),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[UserPublic]:
    """Find people to message. An empty query returns an empty list."""
    users = user_service.search_users(
        db, query=q, exclude_user_id=current_user.id, limit=limit
    )
    return [UserPublic.model_validate(user) for user in users]


# Declared after /search and /me so those literal paths are matched first;
# FastAPI resolves routes in declaration order, and "/users/search" would
# otherwise be read as a user id and fail to parse.
@router.get("/{user_id}", response_model=UserPublic)
def read_user(user_id: int, db: DbSession, current_user: CurrentUser) -> UserPublic:
    """Another user's public profile."""
    return UserPublic.model_validate(user_service.get_user(db, user_id))
