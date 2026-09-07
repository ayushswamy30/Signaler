"""Authentication: login, session issuing, refresh rotation, logout."""

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthenticationError
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.mixins import utcnow
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import user_service

# One message for "no such user" and for "wrong password". Distinguishing them
# would turn the login form into an account-existence oracle.
INVALID_CREDENTIALS = "Incorrect username or password."

# A syntactically valid bcrypt hash that no password matches. Verifying against
# it costs a real bcrypt round, which is the point: see authenticate().
DUMMY_HASH = "$2b$12$" + "." * 53


class IssuedSession:
    """The pair of tokens handed back after a successful login or refresh."""

    def __init__(self, user: User, access_token: str, refresh_token: str) -> None:
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = settings.access_token_expire_minutes * 60


def _is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > utcnow()


def _register_failure(db: Session, user: User) -> None:
    """Count a failed attempt and lock the account if it crosses the threshold."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.max_failed_logins:
        user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
        # Reset the counter along with the lock, so the next lock needs another
        # full run of failures rather than tripping on the very next attempt.
        user.failed_login_attempts = 0
    db.commit()


def authenticate(db: Session, *, username: str, password: str) -> User:
    """Return the user matching these credentials, or raise AuthenticationError.

    The password is verified even when the account is locked out, so the
    response time does not reveal the lock. The lock still wins.
    """
    user = user_service.find_by_username(db, username)
    if user is None:
        # Hash a throwaway value so a missing account costs about the same time
        # as a wrong password; otherwise the timing enumerates accounts.
        verify_password(password, DUMMY_HASH)
        raise AuthenticationError(INVALID_CREDENTIALS)

    password_ok = verify_password(password, user.password_hash)

    if _is_locked(user):
        raise AuthenticationError("Too many failed sign-in attempts. Try again in a few minutes.")
    if not password_ok:
        _register_failure(db, user)
        raise AuthenticationError(INVALID_CREDENTIALS)

    if user.failed_login_attempts:
        user.failed_login_attempts = 0
        db.commit()
    return user


def issue_session(db: Session, user: User, *, user_agent: str | None = None) -> IssuedSession:
    """Mint an access token and a fresh refresh token for a user."""
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent[:255] if user_agent else None,
        )
    )
    db.commit()
    return IssuedSession(user, create_access_token(user.id), raw_refresh)


def refresh_session(
    db: Session, *, refresh_token: str, user_agent: str | None = None
) -> IssuedSession:
    """Exchange a refresh token for a new pair, revoking the presented one.

    Rotation is what makes theft survivable: the stolen copy stops working the
    moment either party uses it, and a second use lands on a revoked row.
    """
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if stored is None or not stored.is_active:
        raise AuthenticationError("Session expired. Please sign in again.")

    stored.revoked_at = utcnow()
    db.flush()
    return issue_session(db, stored.user, user_agent=user_agent)


def revoke_session(db: Session, *, refresh_token: str) -> None:
    """Log out one session. Unknown or already-revoked tokens are a no-op.

    Logout is idempotent on purpose: a client retrying after a dropped response
    must not be told its logout failed.
    """
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        db.commit()


def revoke_all_sessions(db: Session, user: User, *, commit: bool = True) -> None:
    """Log a user out everywhere.

    A bulk UPDATE rather than a loop: this runs on password change, where the
    number of live sessions is unbounded and none of them need loading.
    ``commit=False`` lets a caller fold it into a larger transaction.
    """
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if commit:
        db.commit()


def user_from_access_token(db: Session, token: str) -> User:
    """Resolve an access token to the user it names.

    The user is re-read on every request rather than trusted from the token, so
    a deleted account stops working immediately instead of at token expiry.
    """
    try:
        user_id = decode_access_token(token)
    except TokenError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc

    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired token.")
    return user
