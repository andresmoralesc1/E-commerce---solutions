"""Operations router — refunds, inventory, forecast, alerts."""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import TokenData, get_current_user, get_tenant_ids
from app.services.alerts import alert_loss_burning, send_alert
from app.services.refunds_inventory_forecast import (
    get_low_stock,
    get_refund_stats,
    record_refund,
    revenue_forecast,
    upsert_inventory,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


# ─── Refunds ─────────────────────────────────────────────────────────────

class RefundIn(BaseModel):
    tenant_id: UUID
    sku: str
    order_external_id: str
    refund_amount: float
    reason: str = ""


@router.post("/refunds")
async def post_refund(
    body: RefundIn,
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and body.tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    ok = await record_refund(
        body.tenant_id,
        body.sku,
        body.order_external_id,
        body.refund_amount,
        body.reason,
    )
    return {"ok": ok}


@router.get("/refunds/stats")
async def refund_stats(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    return await get_refund_stats(tenant_id, days)


# ─── Inventory ──────────────────────────────────────────────────────────

class InventoryUpdate(BaseModel):
    sku: str
    stock: int = Field(ge=0)
    external_inventory_id: str | None = None


class InventoryBulk(BaseModel):
    items: list[InventoryUpdate]


@router.post("/inventory/update")
async def inventory_update(
    body: InventoryUpdate,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    await upsert_inventory(
        tenant_id, body.sku, body.stock, body.external_inventory_id
    )
    return {"ok": True}


@router.post("/inventory/bulk")
async def inventory_bulk(
    body: InventoryBulk,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    n = 0
    for item in body.items:
        await upsert_inventory(
            tenant_id, item.sku, item.stock, item.external_inventory_id
        )
        n += 1
    return {"ok": True, "updated": n}


@router.get("/inventory/low-stock")
async def low_stock(
    tenant_id: UUID,
    threshold: int = Query(10, ge=1),
    user: TokenData = Depends(get_current_user),
) -> list[dict]:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    return await get_low_stock(tenant_id, threshold)


# ─── Forecasting ─────────────────────────────────────────────────────────

@router.get("/forecast/{sku}")
async def forecast(
    sku: str,
    tenant_id: UUID,
    days_ahead: int = Query(7, ge=1, le=90),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    return await revenue_forecast(tenant_id, sku, days_ahead)


# ─── Alerts ─────────────────────────────────────────────────────────────

class AlertIn(BaseModel):
    text: str
    title: str | None = None
    color: str = "#10b981"
    fields: list[dict[str, Any]] | None = None


@router.post("/alerts/test")
async def alerts_test(
    body: AlertIn,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    return await send_alert(
        tenant_id, body.text, title=body.title, color=body.color, fields=body.fields
    )


@router.post("/alerts/burning")
async def alerts_burning(
    sku: str,
    ad_spend_3d: float,
    margin_pct: float,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    await alert_loss_burning(tenant_id, sku, ad_spend_3d, margin_pct)
    return {"ok": True}