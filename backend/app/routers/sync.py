"""Sync router — disparo manual de sincronizaciones."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.security import TokenData, get_current_user, get_tenant_ids
from app.connectors import shopify, woocommerce, meta_ads, google_ads
from app.services.profitability import refresh_view

router = APIRouter(prefix="/api/sync", tags=["sync"])


async def _resolve_credentials(tenant_id: UUID) -> dict:
    row = await db.fetchrow(
        "SELECT source, credentials FROM tenants WHERE id = $1 AND active = TRUE",
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    return dict(row)


@router.post("/shopify/{tenant_id}/now")
async def sync_shopify(
    tenant_id: UUID,
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso al tenant")

    creds = await _resolve_credentials(tenant_id)
    if creds["source"] != "shopify":
        raise HTTPException(status_code=400, detail="El tenant no es Shopify")

    c = creds["credentials"]
    synced = await shopify.fetch_orders(
        tenant_id=tenant_id,
        shop_domain=c["shop_domain"],
        access_token=c["access_token"],
    )
    return {"ok": True, "tenant_id": str(tenant_id), "synced_orders": synced}


@router.post("/woocommerce/{tenant_id}/now")
async def sync_woocommerce(
    tenant_id: UUID,
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso al tenant")

    creds = await _resolve_credentials(tenant_id)
    if creds["source"] != "woocommerce":
        raise HTTPException(status_code=400, detail="El tenant no es WooCommerce")

    c = creds["credentials"]
    synced = await woocommerce.fetch_orders(
        tenant_id=tenant_id,
        site_url=c["site_url"],
        consumer_key=c["consumer_key"],
        consumer_secret=c["consumer_secret"],
    )
    return {"ok": True, "tenant_id": str(tenant_id), "synced_orders": synced}


@router.post("/shopify/all")
async def sync_shopify_all(user: TokenData = Depends(get_current_user)) -> dict:
    """Sincroniza TODOS los tenants shopify. Pensado para n8n cron."""
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")
    rows = await db.fetch(
        "SELECT id, credentials FROM tenants WHERE source='shopify' AND active=TRUE"
    )
    results = []
    for r in rows:
        c = r["credentials"]
        try:
            n = await shopify.fetch_orders(
                tenant_id=r["id"],
                shop_domain=c["shop_domain"],
                access_token=c["access_token"],
            )
            results.append({"tenant_id": str(r["id"]), "synced": n})
        except Exception as e:
            results.append({"tenant_id": str(r["id"]), "error": str(e)})
    # Refrescar vista al final
    await refresh_view()
    return {"ok": True, "results": results}


@router.post("/woocommerce/all")
async def sync_woocommerce_all(user: TokenData = Depends(get_current_user)) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")
    rows = await db.fetch(
        "SELECT id, credentials FROM tenants WHERE source='woocommerce' AND active=TRUE"
    )
    results = []
    for r in rows:
        c = r["credentials"]
        try:
            n = await woocommerce.fetch_orders(
                tenant_id=r["id"],
                site_url=c["site_url"],
                consumer_key=c["consumer_key"],
                consumer_secret=c["consumer_secret"],
            )
            results.append({"tenant_id": str(r["id"]), "synced": n})
        except Exception as e:
            results.append({"tenant_id": str(r["id"]), "error": str(e)})
    await refresh_view()
    return {"ok": True, "results": results}