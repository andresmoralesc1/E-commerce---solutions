"""Ads sync router — pull spend from Meta + Google."""
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.security import TokenData, get_current_user
from app.connectors import meta_ads, google_ads
from app.services.profitability import refresh_view

router = APIRouter(prefix="/api/ads", tags=["ads"])


@router.post("/meta/sync")
async def sync_meta(
    days_back: int = 1,
    user: TokenData = Depends(get_current_user),
) -> dict:
    """Pull ad spend from Meta Marketing API para todos los tenants con credenciales."""
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")
    rows = await db.fetch(
        """
        SELECT id, credentials FROM tenants
        WHERE source='shopify' AND active=TRUE
          AND credentials ? 'meta_access_token'
        """
    )
    since = date.today() - timedelta(days=days_back)
    until = date.today()
    results = []
    for r in rows:
        c = r["credentials"]
        try:
            n = await meta_ads.fetch_ad_spend(
                tenant_id=r["id"],
                access_token=c["meta_access_token"],
                ad_account_id=c.get("meta_ad_account_id", ""),
                since=since,
                until=until,
            )
            results.append({"tenant_id": str(r["id"]), "synced": n})
        except Exception as e:
            results.append({"tenant_id": str(r["id"]), "error": str(e)})
    await refresh_view()
    return {"ok": True, "results": results}


@router.post("/google/sync")
async def sync_google(
    days_back: int = 1,
    user: TokenData = Depends(get_current_user),
) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")
    rows = await db.fetch(
        """
        SELECT id, credentials FROM tenants
        WHERE source='shopify' AND active=TRUE
          AND credentials ? 'google_refresh_token'
        """
    )
    since = date.today() - timedelta(days=days_back)
    until = date.today()
    results = []
    for r in rows:
        c = r["credentials"]
        try:
            n = await google_ads.fetch_ad_spend(
                tenant_id=r["id"],
                refresh_token=c["google_refresh_token"],
                customer_id=c.get("google_customer_id", ""),
                since=since,
                until=until,
            )
            results.append({"tenant_id": str(r["id"]), "synced": n})
        except Exception as e:
            results.append({"tenant_id": str(r["id"]), "error": str(e)})
    await refresh_view()
    return {"ok": True, "results": results}


@router.post("/seed/synthetic/{tenant_id}")
async def seed_synthetic_ads(
    tenant_id: UUID,
    days_back: int = 30,
    user: TokenData = Depends(get_current_user),
) -> dict:
    """Para Fase 2 / demo: genera ad_spend sintético si el tenant no tiene.
    Útil cuando aún no se conecta Meta/Google real.
    """
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")
    import random
    from datetime import datetime, timezone

    n_existing = await db.fetchval(
        "SELECT COUNT(*) FROM ad_spend WHERE tenant_id = $1", tenant_id
    )
    if n_existing > 0:
        return {"ok": False, "error": "ya hay ad_spend, --force para regenerar"}

    products = await db.fetch(
        "SELECT sku FROM products WHERE tenant_id = $1", tenant_id
    )
    today = datetime.now(timezone.utc).date()
    rows_to_insert = []
    for day_offset in range(days_back):
        d = today - timedelta(days=day_offset)
        for p in products:
            if random.random() > 0.7:
                continue
            spend = random.randint(5000, 80000)
            has_utm = random.random() < 0.8
            rows_to_insert.append((
                tenant_id, d,
                random.choice(["meta", "google"]),
                f"camp_{random.randint(1, 8)}",
                f"Camp {random.randint(1, 8)}",
                p["sku"] if has_utm else None,
                spend,
                random.randint(1000, 50000),
                random.randint(50, 2500),
                random.randint(0, 50),
                "utm" if has_utm else "proportional",
            ))
    if rows_to_insert:
        await db.executemany(
            """
            INSERT INTO ad_spend
              (tenant_id, date, platform, campaign_id, campaign_name,
                sku, spend, impressions, clicks, conversions,
                attribution_method)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            rows_to_insert,
        )
    await refresh_view()
    return {"ok": True, "rows_inserted": len(rows_to_insert)}