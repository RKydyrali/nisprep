"""Wait for PostgreSQL to accept connections before running migrations.

Replaces pg_isready (not present in python slim images) with a small
asyncpg retry loop. Exits non-zero if the DB is unreachable after timeout.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

TIMEOUT_SECONDS = 60
RETRY_DELAY_SECONDS = 2


def _async_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def main() -> None:
    url = _async_url()
    deadline = asyncio.get_event_loop().time() + TIMEOUT_SECONDS
    while True:
        try:
            conn = await asyncpg.connect(url, timeout=5)
            await conn.close()
            print("postgres is ready")
            return
        except Exception as exc:  # noqa: BLE001 - retry until deadline
            if asyncio.get_event_loop().time() >= deadline:
                print(f"postgres not reachable within {TIMEOUT_SECONDS}s: {exc}", file=sys.stderr)
                sys.exit(1)
            await asyncio.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
