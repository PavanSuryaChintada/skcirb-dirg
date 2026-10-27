"""SQLAlchemy engine. Changing DATABASE_URL is the only switch between Postgres and SQLite."""
from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().sqlalchemy_url
    # bounded, so an unreachable database fails instead of hanging; 5s proved too
    # tight for a TLS handshake to a remote pooler on a slow link
    connect_args = {"connect_timeout": 15} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)
