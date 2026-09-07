"""User accounts: creation, lookup, search, profile and presence.

Service-layer convention used across this package: every public function takes
the ``Session`` as its first argument and commits its own work, so a caller --
an HTTP route, a WebSocket handler, or a script -- never has to know whether an
operation touched one table or four.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.mixins import utcnow
from app.models.user import User

# Reserved so a username can never shadow a route segment or an internal
# identity in a UI ("system said ..."). Checked case-insensitively.
RESERVED_USERNAMES = frozenset({"me", "admin", "system", "signaler", "support", "api", "null"})


def normalise_username(username: str) -> str:
    """Usernames are stored and compared in lower case.

    Doing this in one place is what makes "Ayush" and "ayush" the same account
    rather than two accounts that look identical in every list.
    """
    return username.strip().lower()


def get_user(db: Session, user_id: int) -> User:
    """Return a user by id, or raise NotFoundError."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"No user with id {user_id}.")
    return user


def find_by_username(db: Session, username: str) -> User | None:
    """Return the user with this username, or None. Case-insensitive."""
    return db.scalar(select(User).where(User.username == normalise_username(username)))


def find_by_phone(db: Session, phone_number: str) -> User | None:
    """Return the user with this phone number, or None."""
    return db.scalar(select(User).where(User.phone_number == phone_number))


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    phone_number: str | None = None,
) -> User:
    """Register a new account.

    Uniqueness is checked here for a clear error message, but the database's
    unique constraints remain the real guarantee: two concurrent registrations
    can both pass this check, and the second one then fails on commit.
    """
    username = normalise_username(username)
    if username in RESERVED_USERNAMES:
        raise ValidationError(f"The username {username!r} is reserved.")
    if find_by_username(db, username) is not None:
        raise ConflictError("That username is already taken.")
    if phone_number and find_by_phone(db, phone_number) is not None:
        raise ConflictError("That phone number is already registered.")

    user = User(
        username=username,
        display_name=display_name.strip(),
        phone_number=phone_number,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_profile(
    db: Session,
    user: User,
    *,
    display_name: str | None = None,
    about: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Update the editable parts of a profile.

    ``None`` means "leave unchanged", which is why clearing a field is done by
    passing an empty string -- the route schemas use the same convention.
    """
    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            raise ValidationError("Display name cannot be empty.")
        user.display_name = display_name
    if about is not None:
        user.about = about.strip() or None
    if avatar_url is not None:
        user.avatar_url = avatar_url.strip() or None

    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, *, current_password: str, new_password: str) -> None:
    """Replace a user's password after checking the current one.

    Every refresh token is revoked as a side effect: a password change is the
    action someone takes when they think a session is compromised, so leaving
    other sessions alive would defeat the point. Imported locally to keep the
    module dependency one-way (auth_service already depends on this module).
    """
    if not verify_password(current_password, user.password_hash):
        raise ValidationError("Current password is incorrect.")
    if verify_password(new_password, user.password_hash):
        raise ValidationError("The new password must differ from the current one.")

    from app.services import auth_service

    user.password_hash = hash_password(new_password)
    auth_service.revoke_all_sessions(db, user, commit=False)
    db.commit()


def search_users(db: Session, *, query: str, exclude_user_id: int, limit: int = 20) -> list[User]:
    """Find users by username or display name, for the "new message" picker.

    A blank query returns nothing rather than the whole user table: an empty
    search box must not enumerate every account on the server.
    """
    query = query.strip()
    if not query:
        return []

    pattern = f"%{query.lower()}%"
    statement = (
        select(User)
        .where(
            User.id != exclude_user_id,
            or_(
                User.username.like(pattern),
                func.lower(User.display_name).like(pattern),
                User.phone_number == query,
            ),
        )
        .order_by(User.display_name)
        .limit(limit)
    )
    return list(db.scalars(statement))


def set_presence(db: Session, user: User, *, is_online: bool) -> User:
    """Record that a user connected or disconnected.

    ``last_seen`` is stamped on the way out, not on the way in, so an online
    user's last-seen time is the moment their last connection closed.
    """
    user.is_online = is_online
    if not is_online:
        user.last_seen = utcnow()
    db.commit()
    db.refresh(user)
    return user
