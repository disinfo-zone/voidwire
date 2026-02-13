"""Application configuration from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://voidwire:voidwire@localhost:5432/voidwire",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")

    # Site
    site_url: str = Field(default="https://voidwire.disinfo.zone", alias="SITE_URL")
    admin_url: str = Field(default="https://admin.voidwire.disinfo.zone", alias="ADMIN_URL")
    api_url: str = Field(default="https://api.voidwire.disinfo.zone", alias="API_URL")
    timezone: str = Field(default="UTC", alias="TIMEZONE")

    # Pipeline
    pipeline_schedule: str = Field(default="0 5 * * *", alias="PIPELINE_SCHEDULE")
    artifact_retention_days: int = Field(default=90, alias="ARTIFACT_RETENTION_DAYS")

    # Rate limiting
    rate_limit_per_hour: int = Field(default=60, alias="RATE_LIMIT_PER_HOUR")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
