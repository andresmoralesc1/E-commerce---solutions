"""Tenant router — CRUD multi-tenant."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.security import TokenData, get_current_user
from app.schemas.tenants import TenantIn, TenantOut

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantOut])
async def list_tenants(
    user: TokenData = Depends(get_current_user),
) -> list[TenantOut]:
    if user.superuser:
        rows = await db.fetch(
            "SELECT id, name, source, locale, active, created_at FROM tenants ORDER BY created_at DESC"
        )
    else:
        rows = await db.fetch(
            """
            SELECT t.id, t.name, t.source, t.locale, t.active, t.created_at
            FROM tenants t
            JOIN user_tenants ut ON ut.tenant_id = t.id
            WHERE ut.user_id = $1 AND t.active = TRUE
            ORDER BY t.created_at DESC
            """,
            user.user_id,
        )
    return [TenantOut(**dict(r)) for r in rows]


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(
    body: TenantIn,
    user: TokenData = Depends(get_current_user),
) -> TenantOut:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers crean tenants")
    row = await db.fetchrow(
        """
        INSERT INTO tenants (name, source, credentials, settings, locale)
        VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
        RETURNING id, name, source, locale, active, created_at
        """,
        body.name,
        body.source,
        json.dumps(body.credentials),
        json.dumps(body.settings),
        body.locale,
    )
    await db.execute(
        "INSERT INTO user_tenants (user_id, tenant_id, role) VALUES ($1, $2, 'owner')",
        user.user_id,
        row["id"],
    )
    return TenantOut(**dict(row))


@router.delete("/{tenant_id}", status_code=204)
async def deactivate_tenant(
    tenant_id: UUID,
    user: TokenData = Depends(get_current_user),
) -> None:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")
    await db.execute("UPDATE tenants SET active = FALSE WHERE id = $1", tenant_id)