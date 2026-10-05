from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Matches the local development database in compose.yaml. Override outside local development.
    database_url: SecretStr = SecretStr("postgresql+asyncpg://kora:kora@localhost:5432/kora")
    database_echo: bool = False

    @property
    def docs_enabled(self) -> bool:
        """API docs are served only in local and test; there is deliberately no override."""
        return self.environment in ("local", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
