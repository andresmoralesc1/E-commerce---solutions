"""Audit router — consultar historial de acciones ejecutadas."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import db
from app.core.security import TokenData, get_current_user, get_tenant_ids

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    tenant_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: TokenData = Depends(get_current_user),
) -> list[dict]:
    if tenant_id is not None:
        allowed = await get_tenant_ids(user)
        if not user.superuser and tenant_id not in allowed:
            raise HTTPException(status_code=403, detail="Sin acceso")
        rows = await db.fetch(
            """
            SELECT id, tenant_id, actor, action, payload, result, created_at
            FROM audit_log
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            tenant_id, limit,
        )
    elif user.superuser:
        rows = await db.fetch(
            """
            SELECT id, tenant_id, actor, action, payload, result, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    else:
        allowed = await get_tenant_ids(user)
        if not allowed:
            return []
        rows = await db.fetch(
            """
            SELECT id, tenant_id, actor, action, payload, result, created_at
            FROM audit_log
            WHERE tenant_id = ANY($1::uuid[])
            ORDER BY created_at DESC
            LIMIT $2
            """,
            allowed, limit,
        )

    # Parse jsonb fields
    import json as _json
    out = []
    for r in rows:
        d = dict(r)
        for f in ("payload", "result"):
            if isinstance(d.get(f), str):
                try:
                    d[f] = _json.loads(d[f])
                except Exception:
                    d[f] = None
        out.append(d)
    return out