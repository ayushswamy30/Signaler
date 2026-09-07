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

    # Placeholders for the authentication work in a later stage. No auth is
    # implemented yet; these exist so secrets are never hard-coded later on.
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
