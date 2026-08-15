"""Database engine, session and Redis helpers."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def create_engine_from_settings() -> AsyncEngine:
    """Create an async SQLAlchemy engine bound to the current settings."""
    kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "echo": settings.debug and settings.env == "dev",
    }
    if not settings.database_url.startswith("sqlite"):
        kwargs.update(pool_size=10, max_overflow=20)
    return create_async_engine(settings.database_url, **kwargs)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily build (or reuse) the engine for the current database_url."""
    global _engine, _session_factory
    if _engine is None or str(_engine.url) != settings.database_url:
        _engine = create_engine_from_settings()
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async session (committed by services)."""
    async with get_session_factory()() as session:
        yield session


async def init_db() -> None:
    """Create all tables if the DB is empty (dev bootstrap / first deploy)."""
    from sqlalchemy import text

    from app.models import Base

    engine = get_engine()
    async with engine.connect() as conn:
        try:
            await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
        except Exception:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await conn.close()


def create_redis_client() -> aioredis.Redis:
    """Build a standalone Redis client for direct use (bot handlers, worker)."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency: Redis client for the request, closed on teardown."""
    client = create_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def redis_get_json(redis: aioredis.Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def redis_set_json(redis: aioredis.Redis, key: str, value: Any, ttl: int | None = None) -> None:
    raw = json.dumps(value)
    await redis.set(key, raw, ex=ttl)
