"""Password hashing and token issuing.

Everything cryptographic lives here so no other module has to decide how a
password is hashed or how a token is signed.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# Distinguishes an access token from any other JWT this application might sign
# later, so a token minted for one purpose cannot be replayed for another.
ACCESS_TOKEN_TYPE = "access"

# bcrypt truncates silently at 72 bytes: a 200-character password would have
# the same hash as its first 72 bytes. Rejecting is safer than truncating, and
# the schemas enforce a shorter maximum anyway.
BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or the wrong type."""


def hash_password(password: str) -> str:
    """Return a bcrypt hash of ``password``.

    The salt and work factor are embedded in the returned string, so verifying
    needs nothing but the hash itself.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password exceeds {BCRYPT_MAX_BYTES} bytes, which bcrypt cannot hash.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check ``password`` against a stored bcrypt hash.

    Returns False rather than raising on a malformed or truncated hash: a
    corrupt row must fail authentication, not the request.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: int, expires_delta: timedelta | None = None) -> str:
    """Sign a short-lived access token identifying ``subject`` (a user id)."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        # "sub" is conventionally a string in the JWT spec, and PyJWT enforces
        # it; callers get the integer back from decode_access_token.
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": ACCESS_TOKEN_TYPE,
        # A unique id per token, so a future revocation list has something to
        # key on without invalidating every token for a user.
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """Return the user id carried by a valid access token.

    Raises TokenError for anything that is not a currently valid access token,
    so callers never have to distinguish PyJWT's exception hierarchy.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            # A list, so the token cannot pick its own algorithm -- the "alg:
            # none" and HS/RS confusion attacks both work by doing exactly that.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenError("Token is not an access token.")

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("Token subject is not a user id.") from exc


def generate_refresh_token() -> str:
    """Create a new opaque refresh token.

    Not a JWT: a refresh token must be revocable, and revoking a self-contained
    signed token means keeping a deny-list anyway. 32 bytes of urandom.
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage.

    SHA-256 rather than bcrypt: the token is already 256 bits of uniform
    randomness, so it is not guessable and needs no work factor -- and refresh
    happens often enough that a deliberately slow hash would be felt.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_tokens_match(token: str, stored_hash: str) -> bool:
    """Constant-time comparison of a presented refresh token to a stored hash."""
    return hmac.compare_digest(hash_refresh_token(token), stored_hash)
