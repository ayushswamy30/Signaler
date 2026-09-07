"""User and profile schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

# Letters, digits, underscore and dot; must start with a letter. Narrow on
# purpose: a username appears in URLs and mentions, so anything that would need
# escaping there is rejected at the door.
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{2,49}$")

# E.164-ish: an optional +, then 7 to 15 digits. Deliberately not a full
# validation -- that needs a phone-number library and a region, and getting it
# half right rejects legitimate numbers.
PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")

# The lower bound the registration form promises. bcrypt caps at 72 bytes, so
# the upper bound is not arbitrary -- see app/core/security.py.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72


def validate_username(value: str) -> str:
    """Normalise to lower case and enforce the username shape."""
    value = value.strip().lower()
    if not USERNAME_PATTERN.match(value):
        raise ValueError(
            "Username must start with a letter and use 3-50 letters, digits, dots or underscores."
        )
    return value


def validate_password(value: str) -> str:
    """Enforce length only.

    No character-class rules: they push people towards predictable
    substitutions without adding real entropy, and length is what bcrypt cares
    about. The upper bound is bcrypt's own truncation point.
    """
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(value.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} bytes.")
    return value


class UserPublic(ORMModel):
    """A user as anyone else in a shared conversation may see them."""

    id: int
    username: str
    display_name: str
    avatar_url: str | None = None
    about: str | None = None
    is_online: bool
    last_seen: datetime | None = None


class UserMe(UserPublic):
    """The signed-in user's own record, which adds their private fields."""

    phone_number: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    """A profile edit. Omitted fields are left alone; empty strings clear."""

    display_name: str | None = Field(default=None, max_length=100)
    about: str | None = Field(default=None, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=512)


class PasswordChange(BaseModel):
    """A password change, which requires proving the current password."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, value: str) -> str:
        return validate_password(value)
