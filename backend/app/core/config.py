"""Application configuration loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the Signaler backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Signaler API"
    environment: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./signaler.db"

    # Comma-separated in the environment, e.g. "http://localhost:3000,http://127.0.0.1:3000".
    cors_origins: str = "http://localhost:3000"

    # Authentication. The secret MUST be replaced outside development: every
    # access token in circulation is forgeable by anyone who knows it.
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    # Refresh tokens are opaque random strings stored hashed; this is how long
    # a session may be idle before the user must sign in again.
    refresh_token_expire_days: int = 30

    # Brute-force protection. After this many consecutive failures a login is
    # refused for lockout_minutes, whether or not the password is right.
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # bcrypt work factor. 12 is the common default; tests override it downward
    # because hashing dominates their runtime otherwise.
    bcrypt_rounds: int = 12

    # Page size ceiling shared by every list endpoint, so no caller can ask the
    # database for an unbounded result set.
    max_page_size: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
