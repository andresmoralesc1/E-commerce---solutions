"""WooCommerce connector — REST API v3."""
from typing import Any
from uuid import UUID

import httpx
from datetime import datetime

from app.core import db
from app.core.logging import log


async def fetch_orders(
    tenant_id: UUID,
    site_url: str,
    consumer_key: str,
    consumer_secret: str,
    since: datetime | None = None,
) -> int:
    """Pull orders from WooCommerce REST API."""
    auth = (consumer_key, consumer_secret)
    synced = 0
    page = 1
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params: dict[str, Any] = {"per_page": 100, "page": page}
            if since:
                params["after"] = since.isoformat()
            r = await client.get(
                f"{site_url.rstrip('/')}/wp-json/wc/v3/orders",
                params=params,
                auth=auth,
            )
            if r.status_code != 200:
                log.warning("woo.api_error", status=r.status_code, body=r.text[:200])
                break
            orders = r.json()
            if not orders:
                break
            for order in orders:
                synced += await _upsert_order(tenant_id, order)
            page += 1
    log.info("woocommerce.sync_done", tenant_id=str(tenant_id), synced=synced)
    return synced


async def _upsert_order(tenant_id: UUID, order: dict) -> int:
    external_id = str(order["id"])
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO orders
                  (tenant_id, external_id, customer_email, status, currency,
                   subtotal, discount_total, shipping_cost, tax_total, total, placed_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (tenant_id, external_id) DO UPDATE
                  SET status = EXCLUDED.status, total = EXCLUDED.total, updated_at = NOW()
                RETURNING id
                """,
                tenant_id,
                external_id,
                order.get("billing", {}).get("email"),
                order.get("status"),
                order.get("currency", "COP"),
                float(order.get("subtotal", "0") or 0),
                float(order.get("discount_total", "0") or 0),
                float(order.get("shipping_total", "0") or 0),
                float(order.get("total_tax", "0") or 0),
                float(order.get("total", "0") or 0),
                order.get("date_created"),
            )
    for li in order.get("line_items", []):
        sku = li.get("sku") or f"WOO-{li.get('product_id')}"
        qty = li.get("quantity", 1)
        unit = float(li.get("price", 0))
        await db.execute(
            """
            INSERT INTO order_items
              (order_id, sku, quantity, unit_price, total_price)
            SELECT id, $1, $2, $3, $4 FROM orders
            WHERE tenant_id = $5 AND external_id = $6
              AND NOT EXISTS (
                SELECT 1 FROM order_items oi
                WHERE oi.order_id = orders.id AND oi.sku = $1
              )
            """,
            sku, qty, unit, unit * qty, tenant_id, external_id,
        )
    return 1