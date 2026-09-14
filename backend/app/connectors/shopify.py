"""Shopify connector — Admin API (GraphQL).

Fase 1: scaffold + función de sync manual.
Fase 2: completar queries, webhooks.
"""
from typing import Any
from uuid import UUID

import httpx

from app.core import db
from app.core.logging import log

SHOPIFY_API_VERSION = "2024-10"


async def _shopify_client(shop_domain: str, access_token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"https://{shop_domain}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}",
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def fetch_orders(
    tenant_id: UUID,
    shop_domain: str,
    access_token: str,
    since: str | None = None,
) -> int:
    """Pull orders from Shopify. Returns count synced."""
    query = """
      query($cursor: String) {
        orders(first: 50, after: $cursor, sortKey: UPDATED_AT) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id name email createdAt updatedAt displayFinancialStatus
              currencyCode totalPriceSet { shopMoney { amount currencyCode } }
              subtotalPriceSet { shopMoney { amount currencyCode } }
              totalDiscountsSet { shopMoney { amount currencyCode } }
              totalShippingPriceSet { shopMoney { amount currencyCode } }
              totalTaxSet { shopMoney { amount currencyCode } }
              lineItems(first: 50) {
                edges { node { id sku title quantity originalUnitPriceSet { shopMoney { amount } } } }
              }
            }
          }
        }
      }
    """
    synced = 0
    cursor = None
    async with await _shopify_client(shop_domain, access_token) as client:
        while True:
            payload = {"query": query, "variables": {"cursor": cursor}}
            r = await client.post("/graphql.json", json=payload)
            if r.status_code != 200:
                log.warning("shopify.api_error", status=r.status_code, body=r.text[:200])
                break
            data = r.json()
            orders = data.get("data", {}).get("orders", {})
            for edge in orders.get("edges", []):
                node = edge["node"]
                synced += await _upsert_order(tenant_id, node)
            page = orders.get("pageInfo", {})
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
    log.info("shopify.sync_done", tenant_id=str(tenant_id), synced=synced)
    return synced


async def _upsert_order(tenant_id: UUID, node: dict) -> int:
    """Upsert un pedido + line items a Postgres."""
    external_id = node["id"]
    total_money = node["totalPriceSet"]["shopMoney"]
    subtotal_money = node["subtotalPriceSet"]["shopMoney"]
    discount_money = node["totalDiscountsSet"]["shopMoney"]
    shipping_money = node["totalShippingPriceSet"]["shopMoney"]
    tax_money = node["totalTaxSet"]["shopMoney"]

    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO orders
                  (tenant_id, external_id, customer_email, status, currency,
                   subtotal, discount_total, shipping_cost, tax_total, total, placed_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (tenant_id, external_id) DO UPDATE
                  SET status = EXCLUDED.status,
                      total = EXCLUDED.total,
                      updated_at = NOW()
                RETURNING id
                """,
                tenant_id,
                external_id,
                node.get("email"),
                node.get("displayFinancialStatus"),
                total_money["currencyCode"],
                float(subtotal_money["amount"]),
                float(discount_money["amount"]),
                float(shipping_money["amount"]),
                float(tax_money["amount"]),
                float(total_money["amount"]),
                node["createdAt"],
            )

    # line items — versión simple (sin upsert de product_id)
    for edge in node.get("lineItems", {}).get("edges", []):
        li = edge["node"]
        sku = li.get("sku") or f"SHOPIFY-{li['id']}"
        unit_price = float(li["originalUnitPriceSet"]["shopMoney"]["amount"])
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
            sku,
            li.get("quantity", 1),
            unit_price,
            unit_price * li.get("quantity", 1),
            tenant_id,
            external_id,
        )
    return 1