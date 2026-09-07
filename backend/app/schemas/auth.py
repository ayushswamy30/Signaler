"""Registration, login and session schemas."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import (
    PHONE_PATTERN,
    UserMe,
    validate_password,
    validate_username,
)


class RegisterRequest(BaseModel):
    """A new account."""

    username: str
    password: str
    display_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=32)

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        return validate_username(value)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().replace(" ", "").replace("-", "")
        if not value:
            return None
        if not PHONE_PATTERN.match(value):
            raise ValueError("Enter a phone number as 7-15 digits, optionally starting with +.")
        return value


class LoginRequest(BaseModel):
    """Credentials presented at sign-in.

    Neither field is shape-validated: rejecting a malformed username here would
    tell an attacker which strings are not accounts, and a legacy password must
    still be usable after the rules tighten.
    """

    username: str
    password: str


class RefreshRequest(BaseModel):
    """A refresh token being exchanged, or a session being logged out."""

    refresh_token: str


class TokenResponse(BaseModel):
    """What a successful login, registration or refresh returns.

    The user is included so the client does not need a second round trip to
    render the shell it is about to show.
    """

    access_token: str
    refresh_token: str
    # Named for the OAuth2 bearer convention the Authorization header follows,
    # so clients that already speak it need no special casing.
    token_type: str = "bearer"
    expires_in: int
    user: UserMe
