"""Ads executor — ejecuta acciones reales sobre Meta/Google Ads.

Cada función:
1. Lee credenciales del tenant en `tenants.credentials`
2. Llama al SDK (Meta o Google)
3. Si no hay credenciales / falla, log y registra fallback

Soporta acciones:
- pause_ads
- scale_budget
- increase_price (via Shopify o Woo)
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.connectors import google_ads, meta_ads, shopify as shopify_conn
from app.core import db
from app.core.logging import log


async def _tenant_credentials(tenant_id: UUID) -> dict:
    row = await db.fetchrow(
        "SELECT credentials, source FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row:
        return {}
    creds = row["credentials"]
    if isinstance(creds, str):
        try:
            creds = json.loads(creds)
        except Exception:
            creds = {}
    if not isinstance(creds, dict):
        creds = {}
    return creds


async def _campaign_for_sku(
    tenant_id: UUID, sku: str, platform: str = "meta"
) -> str | None:
    """Devuelve el campaign_id más reciente que haya tenido ad spend para este SKU."""
    row = await db.fetchrow(
        """
        SELECT campaign_id FROM ad_spend
        WHERE tenant_id = $1 AND sku = $2 AND platform = $3
        ORDER BY date DESC LIMIT 1
        """,
        tenant_id, sku, platform,
    )
    return row["campaign_id"] if row else None


async def execute_action(tenant_id: UUID, action: dict) -> dict[str, Any]:
    """Ejecuta la acción aprobada sobre la plataforma de ads correcta."""
    action_type = action["action_type"]
    payload = action.get("payload") or {}
    sku = action.get("sku")
    creds = await _tenant_credentials(tenant_id)

    log.info(
        "ads.execute.start",
        tenant_id=str(tenant_id),
        action_type=action_type,
        sku=sku,
    )

    if action_type == "pause_ads":
        return await _pause_ads(tenant_id, sku, payload, creds)
    if action_type == "scale_budget":
        return await _scale_budget(tenant_id, sku, payload, creds)
    if action_type == "increase_price":
        return await _increase_price(tenant_id, sku, payload, creds)
    if action_type == "renegotiate_cogs":
        return {"status": "noted", "note": "negociación manual con proveedor"}

    return {"status": "unknown_action", "action_type": action_type}


# ─── pause_ads ───────────────────────────────────────────────────────────

async def _pause_ads(
    tenant_id: UUID, sku: str | None, payload: dict, creds: dict
) -> dict:
    results: list[dict] = []

    # Meta
    meta_token = creds.get("meta_access_token")
    campaign_id = payload.get("campaign_id")
    # Si no hay campaign_id en payload, buscamos por SKU en ad_spend
    if not campaign_id and sku:
        campaign_id = await _campaign_for_sku(tenant_id, sku, "meta")

    if meta_token and campaign_id:
        try:
            r = await meta_ads.pause_campaign(meta_token, campaign_id)
            results.append({"platform": "meta", "campaign_id": campaign_id, "result": r})
        except Exception as e:
            log.warning("meta.pause_failed", error=str(e))
            results.append({"platform": "meta", "error": str(e)})

    # Google
    google_refresh = creds.get("google_refresh_token")
    google_customer = creds.get("google_customer_id")
    if not campaign_id and sku:
        # Buscar también para Google
        g_campaign = await _campaign_for_sku(tenant_id, sku, "google")
    else:
        g_campaign = campaign_id

    if google_refresh and g_campaign and google_customer:
        try:
            from app.core.config import settings
            access_token = await google_ads._ensure_access_token(
                settings.google_client_id or creds.get("google_client_id", ""),
                settings.google_client_secret or creds.get("google_client_secret", ""),
                google_refresh,
            )
            r = await google_ads.pause_campaign(
                google_customer, access_token,
                settings.google_developer_token or creds.get("google_developer_token", ""),
                g_campaign,
            )
            results.append({"platform": "google", "campaign_id": g_campaign, "result": r})
        except Exception as e:
            log.warning("google.pause_failed", error=str(e))
            results.append({"platform": "google", "error": str(e)})

    if not results:
        return {
            "status": "noop_no_creds",
            "note": (
                "No hay credenciales Meta/Google configuradas para este tenant. "
                "Conecta Meta/Google via /api/auth/{platform}/start"
            ),
        }

    return {
        "status": "executed",
        "campaigns_paused": [r.get("campaign_id") for r in results if "result" in r],
        "details": results,
    }


# ─── scale_budget ────────────────────────────────────────────────────────

async def _scale_budget(
    tenant_id: UUID, sku: str | None, payload: dict, creds: dict
) -> dict:
    pct = int(payload.get("new_budget_pct", 20))
    campaign_id = payload.get("campaign_id")
    if not campaign_id and sku:
        # Por defecto, escalamos en Meta (si existe)
        campaign_id = await _campaign_for_sku(tenant_id, sku, "meta")

    meta_token = creds.get("meta_access_token")
    if meta_token and campaign_id:
        try:
            r = await meta_ads.scale_campaign_budget(meta_token, campaign_id, pct)
            return {
                "status": "executed",
                "platform": "meta",
                "campaign_id": campaign_id,
                "pct_increase": pct,
                "result": r,
            }
        except Exception as e:
            log.warning("meta.scale_failed", error=str(e))
            return {"status": "failed", "platform": "meta", "error": str(e)}

    google_refresh = creds.get("google_refresh_token")
    google_customer = creds.get("google_customer_id")
    g_campaign = await _campaign_for_sku(tenant_id, sku, "google") if sku else None

    if google_refresh and g_campaign and google_customer:
        try:
            from app.core.config import settings
            access_token = await google_ads._ensure_access_token(
                settings.google_client_id or creds.get("google_client_id", ""),
                settings.google_client_secret or creds.get("google_client_secret", ""),
                google_refresh,
            )
            r = await google_ads.scale_campaign_budget(
                google_customer, access_token,
                settings.google_developer_token or creds.get("google_developer_token", ""),
                g_campaign, pct,
            )
            return {
                "status": "executed",
                "platform": "google",
                "campaign_id": g_campaign,
                "pct_increase": pct,
                "result": r,
            }
        except Exception as e:
            return {"status": "failed", "platform": "google", "error": str(e)}

    return {
        "status": "noop_no_creds",
        "note": "Configura credenciales Meta/Google vía /api/auth/{platform}/start",
    }


# ─── increase_price (Shopify only) ───────────────────────────────────────

async def _increase_price(
    tenant_id: UUID, sku: str | None, payload: dict, creds: dict
) -> dict:
    pct = float(payload.get("new_price_pct", 10))

    # Solo soportado para Shopify en Fase 3
    source = await db.fetchval(
        "SELECT source FROM tenants WHERE id = $1", tenant_id
    )
    if source != "shopify":
        return {
            "status": "noop_unsupported_source",
            "note": f"increase_price solo soportado para Shopify (tenant es {source})",
        }

    shop_domain = creds.get("shop_domain")
    access_token = creds.get("access_token")
    if not (shop_domain and access_token):
        return {
            "status": "noop_no_shopify_creds",
            "note": "Conecta Shopify vía POST /api/sync/shopify o vía /api/tenants/{id}",
        }

    # Buscar variant_id por SKU
    variant_id = await _shopify_variant_for_sku(tenant_id, sku, access_token, shop_domain)
    if not variant_id:
        return {"status": "variant_not_found", "sku": sku}

    # Leer precio actual
    current = await _shopify_get_variant_price(
        variant_id, access_token, shop_domain
    )
    new_price = round(current * (1 + pct / 100), 2)
    result = await shopify_conn.update_variant_price(
        variant_id, new_price, access_token, shop_domain
    )
    return {
        "status": "executed",
        "platform": "shopify",
        "variant_id": variant_id,
        "old_price": current,
        "new_price": new_price,
        "pct_increase": pct,
        "result": result,
    }


async def _shopify_variant_for_sku(
    tenant_id: UUID, sku: str | None, access_token: str, shop_domain: str
) -> str | None:
    row = await db.fetchrow(
        "SELECT external_id FROM products WHERE tenant_id = $1 AND sku = $2",
        tenant_id, sku,
    )
    if not row or not row["external_id"]:
        # Fallback: buscar por SKU via Shopify
        return None
    return row["external_id"]


async def _shopify_get_variant_price(
    variant_id: str, access_token: str, shop_domain: str
) -> float:
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"https://{shop_domain}.myshopify.com/admin/api/2024-10/variants/{variant_id}.json",
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            },
        )
        if r.status_code != 200:
            return 0.0
        return float(r.json().get("variant", {}).get("price", 0))


# ─── Audit log helper ────────────────────────────────────────────────────

async def record_audit(
    tenant_id: UUID | None,
    actor: str,
    action: str,
    payload: dict,
    result: dict | None = None,
) -> None:
    """Inserta una fila en audit_log."""
    await db.execute(
        """
        INSERT INTO audit_log (tenant_id, actor, action, payload, result)
        VALUES ($1::uuid, $2, $3, $4::jsonb, $5::jsonb)
        """,
        tenant_id, actor, action,
        json.dumps(payload),
        json.dumps(result) if result else None,
    )