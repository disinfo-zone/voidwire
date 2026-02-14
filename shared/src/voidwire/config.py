"""Application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


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
    pipeline_run_on_start: bool = Field(default=False, alias="PIPELINE_RUN_ON_START")
    artifact_retention_days: int = Field(default=90, alias="ARTIFACT_RETENTION_DAYS")

    # Backup
    backup_dir: str = Field(default="./backups", alias="BACKUP_DIR")

    # Rate limiting
    rate_limit_per_hour: int = Field(default=60, alias="RATE_LIMIT_PER_HOUR")
    setup_guard_recheck_seconds: int = Field(default=30, alias="SETUP_GUARD_RECHECK_SECONDS")
    skip_setup_guard: bool = Field(default=False, alias="SKIP_SETUP_GUARD")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings (useful in tests)."""
    get_settings.cache_clear()
