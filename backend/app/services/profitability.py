"""Profitability service — refresh + read materialised view."""
from typing import Any
from uuid import UUID

from app.core import db


async def refresh_view(tenant_id: UUID | None = None) -> None:
    """Refresca la vista materializada global.

    Para Fase 1 refrescamos TODO (multi-tenant pequeño). Si crece,
    agregar particiones por tenant_id usando CONCURRENTLY.
    """
    if tenant_id is None:
        await db.execute("REFRESH MATERIALIZED VIEW profitability_mv")
    else:
        # Forzar refresh global (la vista no está particionada en fase 1)
        await db.execute("REFRESH MATERIALIZED VIEW profitability_mv")


async def list_profitability(
    tenant_id: UUID | None = None,
    state: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lee profitability_mv aplicando filtros."""
    where = []
    args: list = []

    if tenant_id is not None:
        args.append(tenant_id)
        where.append(f"tenant_id = ${len(args)}")

    if state is not None:
        args.append(state)
        where.append(f"classify_sku(net_margin_pct) = ${len(args)}")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    args.append(limit)
    args.append(offset)

    query = f"""
        SELECT
          product_id, tenant_id, sku, title, stock,
          revenue_30d, cogs_total, shipping_total, gateway_fee_total,
          ad_spend_total, ad_spend_3d, refunds_total,
          units_sold, orders_count,
          net_margin_abs, net_margin_pct, roas_real,
          classify_sku(net_margin_pct) AS state
        FROM profitability_mv
        {where_sql}
        ORDER BY net_margin_pct ASC NULLS LAST
        LIMIT ${len(args) - 1} OFFSET ${len(args)}
    """
    rows = await db.fetch(query, *args)
    return [dict(r) for r in rows]


async def kpis(tenant_id: UUID | None = None) -> dict[str, Any]:
    where = ""
    args: list = []
    if tenant_id is not None:
        args.append(tenant_id)
        where = f"WHERE tenant_id = ${len(args)}"

    row = await db.fetchrow(
        f"""
        SELECT
          COALESCE(SUM(revenue_30d), 0)        AS revenue_total,
          COALESCE(SUM(net_margin_abs), 0)      AS net_margin_total,
          COALESCE(SUM(ad_spend_total), 0)      AS ad_spend_total,
          COALESCE(SUM(cogs_total), 0)          AS cogs_total,
          COUNT(*)                              AS sku_total,
          COUNT(*) FILTER (WHERE net_margin_pct <= 0 AND ad_spend_3d > 0) AS skus_burning,
          COALESCE(SUM(
            CASE WHEN net_margin_pct <= 0 AND ad_spend_3d > 0
                 THEN ad_spend_3d ELSE 0 END
          ), 0) AS money_burned_3d
        FROM profitability_mv
        {where}
        """,
        *args,
    )
    return dict(row) if row else {}


async def get_sku(tenant_id: UUID, sku: str) -> dict[str, Any] | None:
    row = await db.fetchrow(
        """
        SELECT
          product_id, tenant_id, sku, title, stock,
          revenue_30d, cogs_total, shipping_total, gateway_fee_total,
          ad_spend_total, ad_spend_3d, refunds_total,
          units_sold, orders_count,
          net_margin_abs, net_margin_pct, roas_real,
          classify_sku(net_margin_pct) AS state
        FROM profitability_mv
        WHERE tenant_id = $1 AND sku = $2
        """,
        tenant_id,
        sku,
    )
    return dict(row) if row else None