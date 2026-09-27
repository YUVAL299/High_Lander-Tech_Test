"""Runtime configuration, read from environment variables (prefix ``HL_``)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HL_", env_file=".env", extra="ignore")

    app_name: str = "High Lander"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
