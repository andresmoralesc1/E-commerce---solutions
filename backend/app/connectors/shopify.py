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

# Variants
VARIANT_QUERY = """
  query($id: ID!) {
    productVariant(id: $id) {
      id title price sku
    }
  }
"""

VARIANT_UPDATE = """
  mutation updateVariantPrice($input: ProductVariantInput!) {
    productVariantUpdate(input: $input) {
      productVariant { id price }
      userErrors { field message }
    }
  }
"""


async def get_variant(variant_id: str, access_token: str, shop_domain: str) -> dict:
    """Lee un variant por ID GraphQL."""
    async with await _shopify_client(shop_domain, access_token) as client:
        gid = (
            f"gid://shopify/ProductVariant/{variant_id}"
            if not variant_id.startswith("gid://")
            else variant_id
        )
        r = await client.post(
            "/graphql.json",
            json={"query": VARIANT_QUERY, "variables": {"id": gid}},
        )
        if r.status_code != 200:
            return {}
        return r.json().get("data", {}).get("productVariant", {}) or {}


async def update_variant_price(
    variant_id: str,
    new_price: float,
    access_token: str,
    shop_domain: str,
) -> dict:
    """Actualiza el precio de un variant vía GraphQL."""
    async with await _shopify_client(shop_domain, access_token) as client:
        gid = (
            f"gid://shopify/ProductVariant/{variant_id}"
            if not variant_id.startswith("gid://")
            else variant_id
        )
        r = await client.post(
            "/graphql.json",
            json={
                "query": VARIANT_UPDATE,
                "variables": {
                    "input": {"id": gid, "price": new_price},
                },
            },
        )
        if r.status_code != 200:
            return {"error": r.text[:300]}
        data = r.json()
        errors = (
            data.get("data", {})
            .get("productVariantUpdate", {})
            .get("userErrors", [])
        )
        if errors:
            return {"errors": errors}
        return data.get("data", {}).get("productVariantUpdate", {})


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
    from datetime import datetime
    external_id = str(node["id"])
    total_money = node["totalPriceSet"]["shopMoney"]
    subtotal_money = node["subtotalPriceSet"]["shopMoney"]
    discount_money = node["totalDiscountsSet"]["shopMoney"]
    shipping_money = node["totalShippingPriceSet"]["shopMoney"]
    tax_money = node["totalTaxSet"]["shopMoney"]

    # Normalizar placed_at: viene como ISO string en webhook
    placed_at_raw = node.get("createdAt")
    if isinstance(placed_at_raw, str):
        try:
            placed_at = datetime.fromisoformat(
                placed_at_raw.replace("Z", "+00:00")
            )
        except Exception:
            placed_at = datetime.utcnow()
    elif isinstance(placed_at_raw, datetime):
        placed_at = placed_at_raw
    else:
        placed_at = datetime.utcnow()

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
                placed_at,
            )

    # line items — versión simple (sin upsert de product_id)
    for edge in node.get("lineItems", {}).get("edges", []):
        li = edge["node"]
        sku = str(li.get("sku") or f"SHOPIFY-{li['id']}")
        unit_price = float(li["originalUnitPriceSet"]["shopMoney"]["amount"])
        qty = int(li.get("quantity", 1))
        total_price = unit_price * qty
        await db.execute(
            """
            INSERT INTO order_items
              (order_id, sku, quantity, unit_price, total_price)
            SELECT o.id, $1::text, $2::int, $3::numeric, $4::numeric
            FROM orders o
            WHERE o.tenant_id = $5::uuid AND o.external_id = $6::text
              AND NOT EXISTS (
                SELECT 1 FROM order_items oi
                WHERE oi.order_id = o.id AND oi.sku = $1::text
              )
            """,
            sku,
            qty,
            unit_price,
            total_price,
            tenant_id,
            external_id,
        )
    return 1