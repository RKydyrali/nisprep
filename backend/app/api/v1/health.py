"""Health check endpoint."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_redis, get_session

router = APIRouter(tags=["health"])

VERSION = "1.0.0"


@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_ok = True
    try:
        await redis.ping()
    except Exception:
        redis_ok = False

    return {"status": "ok", "version": VERSION, "db": db_ok, "redis": redis_ok}
