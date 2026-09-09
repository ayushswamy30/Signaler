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

    @property
    def sqlalchemy_url(self) -> str:
        """The database URL in the form SQLAlchemy expects.

        Managed Postgres providers hand out ``postgres://...``, which SQLAlchemy
        has not accepted since 1.4, and a bare ``postgresql://`` selects
        psycopg2 while this project installs psycopg 3. Normalising here means
        ``DATABASE_URL`` can be pasted straight from the provider's dashboard
        -- or bound from a Render blueprint -- without being edited first.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    # Comma-separated in the environment, e.g. "http://localhost:3000,http://127.0.0.1:3000".
    cors_origins: str = "http://localhost:3000"

    # Optional pattern for origins that cannot be listed literally, because the
    # hostname changes per deployment -- Vercel preview builds, for instance.
    # Empty by default: an unanchored or careless pattern here would hand any
    # matching site the ability to make credentialed calls to this API.
    cors_origin_regex: str = ""

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

    # TURN relay for calls that STUN alone cannot connect (symmetric NAT, a
    # strict corporate/carrier firewall -- see /api/calls/ice-servers). Both
    # are the values from a Metered.ca dashboard: the per-account subdomain
    # ("yourapp.metered.ca") and its API key. Left blank, the endpoint still
    # returns Google's public STUN servers, so calls keep working everywhere
    # STUN alone is enough -- only the TURN fallback is missing, and it fails
    # the way "Could not connect" describes rather than 500ing.
    metered_turn_domain: str = ""
    metered_turn_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
