"""Database settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Configure relational persistence."""

    URL: str = "postgresql+asyncpg://boxbox-api:boxbox-api@localhost:5432/boxbox-api"
    AUTO_CREATE_SCHEMA: bool = False

    model_config = SettingsConfigDict(case_sensitive=True, env_prefix="DATABASE_")
