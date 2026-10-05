from functools import lru_cache
from typing import Literal

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
