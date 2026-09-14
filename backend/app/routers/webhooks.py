"""Webhook router — recibe eventos en tiempo real de Shopify/Woo/Evolution."""
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

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
    shop_domain = (xshopify_shop_domain or body.get("shop_domain", "")).rstrip("/")

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

    try:
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
    """Recibe eventos de WhatsApp vía Evolution API v2.

    Formato típico de Evolution webhook (messages.upsert):
    {
      "event": "messages.upsert",
      "instance": "brain",
      "data": {
        "key": {"remoteJid": "573001234567@s.whatsapp.net", "fromMe":": false},
        "pushName": "Andres",
        "message": {"conversation": "SI"},
        "messageType": "conversation"
      },
      "date_time": "2026-09-14T18:00:00.000Z"
    }

    Cuando llega un SI/NO, busca la pending_action más reciente
    del manager (por tenant activo) y la confirma/ejecuta.
    """
    body = await request.json()
    event = body.get("event", "")

    if event != "messages.upsert":
        # connection.update, qrcode.updated, etc. — solo log
        return {"ok": True, "ignored_event": event}

    data = body.get("data", {})
    msg_data = data.get("message", {})
    msg = (
        msg_data.get("conversation")
        or msg_data.get("extendedTextMessage", {}).get("text")
        or ""
    )
    key = data.get("key", {})
    phone = key.get("remoteJid", "").replace("@s.whatsapp.net", "")
    text = (msg or "").strip().upper()
    from_me = key.get("fromMe", False)

    # Ignorar mensajes propios
    if from_me or not text:
        return {"ok": True, "ignored": "self_or_empty"}

    # SI / NO
    if text not in ("SI", "NO", "S", "N", "SÍ"):
        return {"ok": True, "ignored": "not_si_no"}

    approved = text in ("SI", "S", "SÍ")

    from app.core import db
    from app.services.agent_decision import confirm_and_execute

    # Estrategia — buscar pending_action del phone (normalizar a E.164):
    phone_clean = phone.lstrip("+")
    phone_variants = [phone, phone_clean, "+" + phone_clean]
    tenant = await db.fetchrow(
        """
        SELECT id FROM tenants
        WHERE active = TRUE
          AND settings->>'manager_phone' = ANY($1::text[])
        ORDER BY created_at DESC LIMIT 1
        """,
        phone_variants,
    )
    tenant_id = tenant["id"] if tenant else None

    if tenant_id:
        # Más reciente pending_action de ese tenant
        row = await db.fetchrow(
            """
            SELECT id, tenant_id FROM pending_actions
            WHERE tenant_id = $1 AND status = 'pending'
              AND created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id,
        )
    else:
        # Fallback: cualquier pending reciente
        row = await db.fetchrow(
            """
            SELECT id, tenant_id FROM pending_actions
            WHERE status = 'pending'
              AND created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC LIMIT 1
            """
        )

    if not row:
        return {"ok": True, "msg": "no_pending_actions"}

    result = await confirm_and_execute(
        str(row["id"]), approved, actor=f"whatsapp:{phone}"
    )
    return {
        "ok": True,
        "action_id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]) if "tenant_id" in row else None,
        "result": result,
    }