"""Async Postgres connection pool."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from app.core.config import settings
from app.core.logging import log

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Create global connection pool. Idempotent."""
    global _pool
    if _pool is not None:
        return

    log.info("db.init", url_host=settings.database_url.split("@")[-1])
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db() first")
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def fetch(query: str, *args) -> list[asyncpg.Record]:
    async with acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    async with acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    async with acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args) -> str:
    async with acquire() as conn:
        return await conn.execute(query, *args)