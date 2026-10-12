from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The compose.yaml development database. Its credentials are public, so it is local-only.
LOCAL_DATABASE_URL = "postgresql+asyncpg://kora:kora@localhost:5432/kora"


class Settings(BaseSettings):
    """Application settings, read from `KORA_`-prefixed environment variables (or `.env`)."""

    model_config = SettingsConfigDict(
        env_prefix="KORA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "KORA API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False

    # Matches the local development database in compose.yaml. Must be set outside local/test.
    database_url: SecretStr = SecretStr(LOCAL_DATABASE_URL)
    database_echo: bool = False

    @model_validator(mode="after")
    def _deployed_environments_are_safe(self) -> Self:
        """Staging and production refuse to start with the committed local credentials or debug
        mode (which returns tracebacks to clients)."""
        if self.environment in ("staging", "production"):
            if self.database_url.get_secret_value() == LOCAL_DATABASE_URL:
                raise ValueError("KORA_DATABASE_URL must be set explicitly in this environment.")
            if self.debug:
                raise ValueError("KORA_DEBUG must be false in this environment.")
        return self

    @property
    def docs_enabled(self) -> bool:
        """API docs are served only in local and test; there is deliberately no override."""
        return self.environment in ("local", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
