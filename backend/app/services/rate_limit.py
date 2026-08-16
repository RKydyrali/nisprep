"""Redis-based fixed-window rate limiting for auth/session endpoints.

No external dependencies: a simple INCR + EXPIRE against Redis. Every
enforcement raises HTTP 429 with a human-readable message.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request

RATE_LIMIT_MESSAGE = "Слишком много попыток. Подождите немного и повторите."


async def enforce_rate_limit(
    redis,
    bucket: str,
    limit: int,
    window_seconds: int,
    message: str = RATE_LIMIT_MESSAGE,
) -> None:
    """Fixed-window counter: at most ``limit`` events per ``window_seconds``."""
    if redis is None:
        return
    now = int(time.time())
    window = now // window_seconds
    key = f"rl:{bucket}:{window}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds + 1)
    count, _ = await pipe.execute()
    if int(count) > limit:
        raise HTTPException(status_code=429, detail=message)


def client_ip(request: Request) -> str:
    """Best-effort real client IP behind nginx (X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client is not None else "unknown"
