"""Application settings loaded from environment variables (no prefix)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Danyshpan API"
    env: str = "dev"
    debug: bool = True

    database_url: str = "sqlite+aiosqlite:///./danyshpan.db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "danyshpan-dev-secret-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080

    telegram_bot_token: str = ""
    telegram_bot_username: str = "DanyshpanNis_bot"
    webhook_secret: str = ""

    admin_email: str = "admin@danyshpan.xyz"
    admin_password: str = "admin-danyshpan-2024"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://danyshpan.xyz",
    ]

    psi_cutoff: float = 0.0
    frontend_url: str = "https://danyshpan.xyz"
    timezone: str = "Asia/Almaty"

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("jwt_secret must be at least 32 characters long")
        return v

    @field_validator("env")
    @classmethod
    def _env_value(cls, v: str) -> str:
        if v not in ("dev", "prod", "test"):
            raise ValueError("env must be 'dev' or 'prod'")
        return v

    @model_validator(mode="after")
    def _prod_secrets(self) -> "Settings":
        """M10: в проде нельзя использовать известные дефолтные секреты."""
        if self.env == "prod" and self.jwt_secret == (
            "danyshpan-dev-secret-change-me-in-production-0123456789"
        ):
            raise ValueError("JWT_SECRET must be overridden in production")
        if self.env == "prod" and self.admin_password == "admin-danyshpan-2024":
            raise ValueError("ADMIN_PASSWORD must be overridden in production")
        return self

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Map plain sqlite URLs onto the aiosqlite async driver."""
        if v.startswith("sqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if v.startswith("sqlite://"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
