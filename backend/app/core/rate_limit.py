"""Rate limiter simple por tenant.

Límite: 60 requests/min por tenant, 1000/h. Default global: 200/min.

Uso:
    @router.post("/endpoint", dependencies=[Depends(rate_limit_per_tenant)])
    async def endpoint(...): ...
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.core.security import TokenData, get_current_user

# In-memory store (simple). Para producción: Redis con TTL.
_buckets: dict[str, list[float]] = defaultdict(list)

# Config
PER_TENANT_PER_MINUTE = 200
GLOBAL_PER_MINUTE = 1000


def _consume(key: str, max_per_minute: int) -> bool:
    """Consume un slot del bucket. Devuelve True si OK."""
    now = time.time()
    window_start = now - 60
    bucket = _buckets[key]
    # Drop expired
    while bucket and bucket[0] < window_start:
        bucket.pop(0)
    if len(bucket) >= max_per_minute:
        return False
    bucket.append(now)
    return True


async def rate_limit_per_tenant(
    request: Request,
    user: TokenData = Depends(get_current_user),
) -> None:
    """Rate limit basado en tenant del user (superusers bypass)."""
    if user.superuser:
        return  # sin límite para superusers

    from app.core import db
    tenant_ids = await db.fetchval(
        "SELECT array_agg(tenant_id) FROM user_tenants WHERE user_id = $1",
        user.user_id,
    ) or []

    # Limit por user_id (no por tenant, evita abuso con muchos tenants)
    user_key = f"user:{user.user_id}"
    if not _consume(user_key, PER_TENANT_PER_MINUTE):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: {PER_TENANT_PER_MINUTE} req/min per user",
            headers={"Retry-After": "60"},
        )

    # Global limit por IP
    ip = request.client.host if request.client else "unknown"
    if not _consume(f"ip:{ip}", GLOBAL_PER_MINUTE):
        raise HTTPException(
            status_code=429,
            detail="Global rate limit exceeded",
            headers={"Retry-After": "60"},
        )


async def rate_limit_anonymous(
    request: Request,
) -> None:
    """Rate limit para endpoints sin auth (login, /)."""
    ip = request.client.host if request.client else "unknown"
    if not _consume(f"anon:{ip}", 30):
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": "60"},
        )