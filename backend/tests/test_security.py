"""Password hashing and token handling."""

from datetime import timedelta

import jwt
import pytest

from app.core import security
from app.core.config import settings


def test_hash_is_not_the_password():
    hashed = security.hash_password("hunter2000")
    assert hashed != "hunter2000"
    assert hashed.startswith("$2b$")


def test_verify_accepts_the_right_password_and_rejects_others():
    hashed = security.hash_password("hunter2000")
    assert security.verify_password("hunter2000", hashed)
    assert not security.verify_password("hunter2001", hashed)


def test_same_password_hashes_differently_each_time():
    """Distinct salts, so identical passwords are not identifiable from the table."""
    assert security.hash_password("same") != security.hash_password("same")


def test_verify_returns_false_for_a_corrupt_hash():
    """A damaged row must fail authentication, not raise out of the request."""
    assert not security.verify_password("anything", "not-a-bcrypt-hash")


def test_password_longer_than_bcrypt_can_hash_is_rejected():
    """Rejected rather than truncated: silent truncation makes long passwords weaker."""
    with pytest.raises(ValueError):
        security.hash_password("x" * 100)


def test_access_token_round_trips_the_user_id():
    token = security.create_access_token(42)
    assert security.decode_access_token(token) == 42


def test_expired_token_is_rejected():
    token = security.create_access_token(42, expires_delta=timedelta(seconds=-1))
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_token_signed_with_another_secret_is_rejected():
    forged = jwt.encode({"sub": "42", "type": "access"}, "other-secret", algorithm="HS256")
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)


def test_unsigned_token_is_rejected():
    """The "alg: none" attack: a token that declines to be signed at all."""
    forged = jwt.encode({"sub": "42", "type": "access"}, key="", algorithm="none")
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)


def test_token_without_an_expiry_is_rejected():
    """A token with no exp would never age out; decoding requires the claim."""
    forged = jwt.encode(
        {"sub": "42", "type": "access"}, settings.jwt_secret_key, algorithm="HS256"
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)


def test_refresh_tokens_are_stored_hashed_and_compared_constant_time():
    token = security.generate_refresh_token()
    stored = security.hash_refresh_token(token)
    assert stored != token
    assert security.refresh_tokens_match(token, stored)
    assert not security.refresh_tokens_match(security.generate_refresh_token(), stored)
