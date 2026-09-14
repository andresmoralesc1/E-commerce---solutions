"""Refunds service — tracking real de devoluciones Shopify + WooCommerce.

Las devoluciones afectan el margen real (no son "ingresos netos" como
los reports simples). Refund completo = refund_amount + pérdida del envío
+ costo de procesamiento (~15% adicional).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg

from app.core import db
from app.core.logging import log


async def record_refund(
    tenant_id: UUID,
    sku: str,
    order_external_id: str,
    refund_amount: float,
    reason: str = "",
) -> bool:
    """Marca line items del order como refunded y registra el monto."""
    async with db.acquire() as conn:
        async with conn.transaction():
            # Marcar line items como refunded
            await conn.execute(
                """
                UPDATE order_items oi
                SET refunded = TRUE,
                    refund_amount = $1
                FROM orders o
                WHERE oi.order_id = o.id
                  AND o.tenant_id = $2
                  AND o.external_id = $3
                  AND oi.sku = $4
                """,
                refund_amount, tenant_id, order_external_id, sku,
            )
    log.info(
        "refund.recorded",
        tenant_id=str(tenant_id),
        sku=sku,
        order=order_external_id,
        amount=refund_amount,
        reason=reason,
    )
    return True


async def get_refund_stats(
    tenant_id: UUID,
    days: int = 30,
) -> dict[str, Any]:
    """Estadísticas de refunds para el tenant."""
    row = await db.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE refunded)                  AS refunded_items,
          COALESCE(SUM(refund_amount) FILTER (WHERE refunded), 0) AS refund_total,
          COUNT(DISTINCT order_id) FILTER (WHERE refunded) AS refunded_orders
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.tenant_id = $1
          AND o.placed_at >= CURRENT_DATE - ($2 || ' days')::interval
        """,
        tenant_id, str(days),
    )
    return dict(row) if row else {}


# ─── Inventory sync ──────────────────────────────────────────────────────

async def upsert_inventory(
    tenant_id: UUID,
    sku: str,
    stock: int,
    external_inventory_id: str | None = None,
) -> None:
    """Actualiza el stock de un producto desde una fuente externa."""
    await db.execute(
        """
        UPDATE products
        SET stock = $1,
            metadata = metadata || jsonb_build_object(
              'external_inventory_id', $2::text,
              'last_stock_sync', NOW()::text
            ),
            updated_at = NOW()
        WHERE tenant_id = $3 AND sku = $4
        """,
        stock,
        external_inventory_id,
        tenant_id,
        sku,
    )


async def get_low_stock(
    tenant_id: UUID, threshold: int = 10
) -> list[dict[str, Any]]:
    """Productos con stock bajo el threshold."""
    rows = await db.fetch(
        """
        SELECT sku, title, stock, cost
        FROM products
        WHERE tenant_id = $1 AND stock <= $2
        ORDER BY stock ASC
        """,
        tenant_id, threshold,
    )
    return [dict(r) for r in rows]


# ─── Forecasting (basic) ─────────────────────────────────────────────────

async def revenue_forecast(
    tenant_id: UUID,
    sku: str,
    days_ahead: int = 7,
) -> dict[str, Any]:
    """Forecast simple de revenue: media de últimos 14 días × days_ahead.

    Sirve para saber cuánto margen esperar de un SKU en `days_ahead`.
    """
    row = await db.fetchrow(
        """
        WITH daily AS (
          SELECT
            date_trunc('day', o.placed_at) AS day,
            SUM(oi.total_price - oi.discount) AS rev
          FROM order_items oi
          JOIN orders o ON o.id = oi.order_id
          WHERE o.tenant_id = $1 AND oi.sku = $2
            AND o.placed_at >= NOW() - INTERVAL '14 days'
            AND o.status NOT IN ('cancelled','refunded')
          GROUP BY day
        )
        SELECT
          COUNT(*)                AS days_with_data,
          COALESCE(AVG(rev), 0)   AS avg_daily_revenue,
          COALESCE(STDDEV(rev), 0) AS stddev_daily_revenue,
          COALESCE(MAX(rev), 0)   AS max_daily_revenue
        FROM daily
        """,
        tenant_id, sku,
    )
    data = dict(row) if row else {}
    avg = float(data.get("avg_daily_revenue", 0))
    forecast = avg * days_ahead
    return {
        "sku": sku,
        "days_ahead": days_ahead,
        "avg_daily_revenue": avg,
        "stddev_daily_revenue": float(data.get("stddev_daily_revenue", 0)),
        "forecast_revenue": forecast,
        "confidence": "low" if data.get("days_with_data", 0) < 7 else "medium",
    }