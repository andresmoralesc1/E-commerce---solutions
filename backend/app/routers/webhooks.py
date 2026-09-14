"""Webhook router — recibe eventos en tiempo real de Shopify/Woo/Evolution."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
import json

from app.connectors import shopify, woocommerce

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/shopify/orders")
async def shopify_orders_webhook(
    request: Request,
    x_shopify_shop_domain: str | None = Header(None),
    x_shopify_topic: str | None = Header(None),
) -> dict:
    """Recibe webhook de Shopify. Busca tenant por shop_domain y procesa."""
    body = await request.json()
    shop_domain = (x_shopify_shop_domain or body.get("shop_domain", "")).rstrip("/")

    # Buscar tenant por dominio
    # TODO Fase 3: cache de shop_domain -> tenant_id
    # Por ahora lookup en credentials
    from app.core import db

    tenant = await db.fetchrow(
        """
        SELECT id, credentials FROM tenants
        WHERE source='shopify' AND active=TRUE
          AND credentials->>'shop_domain' = $1
        LIMIT 1
        """,
        shop_domain,
    )
    if not tenant:
        return {"ok": False, "error": "tenant_not_found"}

    # Parsear order mínimo desde webhook (estructura real en Fase 3)
    # El webhook trae order data en el body
    try:
        # Forma simplificada — el body es directamente un order
        node = body
        await shopify._upsert_order(tenant["id"], node)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"webhook_error: {e}")

    return {"ok": True, "tenant_id": str(tenant["id"])}


@router.post("/woocommerce/orders")
async def woocommerce_orders_webhook(
    request: Request,
) -> dict:
    body = await request.json()
    # WooCommerce webhooks incluyen el sitio en el body o en headers
    site_url = body.get("site_url") or request.headers.get("x-wc-webhook-source", "")

    from app.core import db

    tenant = await db.fetchrow(
        """
        SELECT id, credentials FROM tenants
        WHERE source='woocommerce' AND active=TRUE
          AND credentials->>'site_url' = $1
        LIMIT 1
        """,
        site_url,
    )
    if not tenant:
        return {"ok": False, "error": "tenant_not_found"}

    try:
        await woocommerce._upsert_order(tenant["id"], body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"webhook_error: {e}")

    return {"ok": True, "tenant_id": str(tenant["id"])}


@router.post("/evolution")
async def evolution_webhook(
    request: Request,
) -> dict:
    """Recibe mensajes de WhatsApp vía Evolution API. Procesa respuestas SI/NO
    a acciones pendientes."""
    body = await request.json()
    # Evolution API v2: data.message.conversation o extendedTextMessage.text
    try:
        msg_data = body.get("data", {})
        msg = (
            msg_data.get("message", {}).get("conversation")
            or msg_data.get("message", {}).get("extendedTextMessage", {}).get("text")
            or ""
        )
        phone = msg_data.get("key", {}).get("remoteJid", "").replace("@s.whatsapp.net", "")
        text = msg.strip().upper()
    except Exception:
        return {"ok": False, "error": "bad_payload"}

    if text not in ("SI", "NO", "S", "N"):
        return {"ok": True, "ignored": True}

    approved = text in ("SI", "S")
    # Buscar pending_action más reciente para ese phone (multi-tenant)
    from app.core import db
    from app.services.agent_decision import confirm_and_execute

    row = await db.fetchrow(
        """
        SELECT id, tenant_id FROM pending_actions
        WHERE status='pending'
          AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if not row:
        return {"ok": True, "msg": "no_pending_actions"}

    # TODO Fase 3: validar que el phone pertenece al manager del tenant
    result = await confirm_and_execute(str(row["id"]), approved, actor=f"whatsapp:{phone}")
    return {"ok": True, "action_id": str(row["id"]), "result": result}