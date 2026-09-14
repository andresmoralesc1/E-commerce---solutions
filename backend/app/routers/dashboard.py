"""Dashboard router — KPIs + profitability."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import TokenData, get_current_user, get_tenant_ids
from app.schemas.dashboard import KPIsOut, ProfitabilityRow
from app.services.profitability import kpis, list_profitability

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=KPIsOut)
async def get_kpis(
    tenant_id: UUID | None = Query(None),
    user: TokenData = Depends(get_current_user),
) -> KPIsOut:
    # Validar acceso
    if tenant_id is not None:
        allowed = await get_tenant_ids(user)
        if not user.superuser and tenant_id not in allowed:
            return KPIsOut(
                revenue_total=0, net_margin_total=0,
                ad_spend_total=0, cogs_total=0,
                sku_total=0, skus_burning=0, money_burned_3d=0,
            )
    data = await kpis(tenant_id)
    return KPIsOut(**(data or {}))


@router.get("/profitability", response_model=list[ProfitabilityRow])
async def get_profitability(
    tenant_id: UUID | None = Query(None),
    state: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: TokenData = Depends(get_current_user),
) -> list[ProfitabilityRow]:
    if tenant_id is not None:
        allowed = await get_tenant_ids(user)
        if not user.superuser and tenant_id not in allowed:
            return []
    rows = await list_profitability(tenant_id, state, limit, offset)
    return [ProfitabilityRow(**r) for r in rows]


@router.post("/refresh")
async def refresh(
    tenant_id: UUID | None = None,
    user: TokenData = Depends(get_current_user),
) -> dict:
    """Refresca la vista materializada. Solo superuser o cron job."""
    if not user.superuser:
        return {"ok": False, "error": "forbidden"}
    from app.services.profitability import refresh_view
    await refresh_view(tenant_id)
    return {"ok": True}