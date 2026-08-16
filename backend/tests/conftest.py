"""Shared fixtures for API tests: isolated sqlite DB, fakeredis stub, seeded data."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from fakeredis import aioredis as fakeredis_aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

os.environ.setdefault("ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{Path(tempfile.mkdtemp()) / 'conftest_default.db'}",
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-chars-long!!")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.dev")
os.environ.setdefault("ADMIN_PASSWORD", "admin-pass-12345")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")

from app.core.config import get_settings  # noqa: E402
from app.db.base import create_engine_from_settings, get_redis, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed_database  # noqa: E402

settings = get_settings()


@pytest_asyncio.fixture
async def db_engine(tmp_path: Path):
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_from_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return factory


@pytest_asyncio.fixture
async def db(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def redis():
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def seeded(db):
    await seed_database(db)
    return db


@pytest_asyncio.fixture
def app_with_overrides(db_session_factory, redis):
    async def _override_session():
        async with db_session_factory() as session:
            yield session

    async def _override_redis():
        yield redis

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_redis] = _override_redis
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_with_overrides):
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
