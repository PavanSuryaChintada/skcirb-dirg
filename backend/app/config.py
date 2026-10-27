"""Env-driven settings. Every value comes from the environment; nothing secret has a default."""
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalise_db_url(url: str) -> str:
    """Point plain Postgres URLs at the psycopg 3 driver.

    Supabase and Heroku hand out postgresql:// or postgres:// URLs, which SQLAlchemy
    maps to psycopg2. We ship psycopg 3, so only the scheme is rewritten; host,
    credentials and query (e.g. ?sslmode=require) are left untouched.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    # Real environment variables only. No .env file is read here: docker compose
    # injects the values, and tests set their own, so tests never see real config.
    model_config = SettingsConfigDict(extra="ignore")

    database_url: SecretStr
    decision_cutoff_hour_utc: int = Field(default=9, ge=0, le=23)
    cors_origins: str = "http://localhost:3000"

    @field_validator("cors_origins")
    @classmethod
    def no_wildcard(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must list origins explicitly, never '*'")
        return value

    @property
    def sqlalchemy_url(self) -> str:
        return normalise_db_url(self.database_url.get_secret_value())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
