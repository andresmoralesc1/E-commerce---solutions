"""Attribution service — UTM content -> SKU, fallback proporcional."""
from uuid import UUID

from app.core import db


async def attribute_spend(
    tenant_id: UUID, campaign_id: str, total_spend: float, date_from, date_to
) -> dict[str, float]:
    """Devuelve {sku: attributed_spend}.

    Si hay UTMs en ad_spend → directo.
    Si no → distribución proporcional al revenue del SKU en el periodo.
    """
    # 1. ¿Tenemos datos atribución por UTM en este camp?
    rows = await db.fetch(
        """
        SELECT sku, SUM(spend) AS s
        FROM ad_spend
        WHERE tenant_id = $1
          AND campaign_id = $2
          AND attribution_method = 'utm'
          AND date BETWEEN $3 AND $4
          AND sku IS NOT NULL
        GROUP BY sku
        """,
        tenant_id,
        campaign_id,
        date_from,
        date_to,
    )
    utm_data = {r["sku"]: float(r["s"]) for r in rows if r["sku"]}

    if utm_data:
        return utm_data

    # 2. Fallback proporcional al revenue
    rev_rows = await db.fetch(
        """
        SELECT oi.sku, SUM(oi.total_price - oi.discount) AS rev
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.tenant_id = $1
          AND o.placed_at BETWEEN $2 AND $3
          AND o.status NOT IN ('cancelled','refunded')
        GROUP BY oi.sku
        """,
        tenant_id,
        date_from,
        date_to,
    )
    total_rev = sum(float(r["rev"]) for r in rev_rows)
    if total_rev <= 0:
        return {}

    return {
        r["sku"]: total_spend * (float(r["rev"]) / total_rev)
        for r in rev_rows
        if r["sku"]
    }