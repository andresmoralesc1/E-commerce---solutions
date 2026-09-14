"""Slack/Discord alerts — notificación alternativa a WhatsApp.

Slack usa Incoming Webhooks (URL del workspace).
Discord usa Webhooks también.
Ambos formatos son compatibles (JSON con campo 'text').
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from app.core import db
from app.core.config import settings
from app.core.logging import log


async def _tenant_webhooks(tenant_id: UUID) -> dict[str, str | None]:
    """Lee webhook URLs del tenant en settings."""
    row = await db.fetchrow(
        "SELECT settings FROM tenants WHERE id = $1", tenant_id
    )
    if not row:
        return {"slack": None, "discord": None}
    s = row["settings"]
    if isinstance(s, str):
        import json as _json
        try:
            s = _json.loads(s)
        except Exception:
            s = {}
    if not isinstance(s, dict):
        s = {}
    return {
        "slack": s.get("slack_webhook_url"),
        "discord": s.get("discord_webhook_url"),
    }


async def send_alert(
    tenant_id: UUID,
    text: str,
    *,
    title: str | None = None,
    color: str = "#10b981",        # green
    fields: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Envía alerta a Slack + Discord del tenant (si configurados)."""
    webhooks = await _tenant_webhooks(tenant_id)
    sent = []
    errors = []

    # Slack (Incoming Webhook)
    if webhooks["slack"]:
        payload = {
            "text": title or "🧠 Ecommerce Brain",
            "attachments": [
                {
                    "color": color,
                    "text": text,
                    "fields": fields or [],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(webhooks["slack"], json=payload)
                sent.append({"platform": "slack", "status": r.status_code})
                if r.status_code >= 400:
                    errors.append({"platform": "slack", "body": r.text[:200]})
        except Exception as e:
            errors.append({"platform": "slack", "error": str(e)})

    # Discord (Webhook)
    if webhooks["discord"]:
        embeds = [{
            "title": title or "🧠 Ecommerce Brain",
            "description": text,
            "color": int(color.lstrip("#"), 16) if color.startswith("#") else 0x10b981,
            "fields": fields or [],
        }]
        payload = {"embeds": embeds}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(webhooks["discord"], json=payload)
                sent.append({"platform": "discord", "status": r.status_code})
                if r.status_code >= 400:
                    errors.append({"platform": "discord", "body": r.text[:200]})
        except Exception as e:
            errors.append({"platform": "discord", "error": str(e)})

    log.info(
        "alert.sent",
        tenant_id=str(tenant_id),
        sent=sent,
        errors=errors,
    )
    return {"sent": sent, "errors": errors}


async def alert_loss_burning(
    tenant_id: UUID, sku: str, ad_spend_3d: float, margin_pct: float
) -> None:
    """Helper: alerta pre-formateada para SKUs a pérdida con ad spend."""
    text = (
        f"🚨 *{sku}* lleva 3 días a pérdida ({margin_pct:.1f}%) "
        f"con ${ad_spend_3d:.0f} en ads. Pausa recomendada."
    )
    await send_alert(
        tenant_id,
        text,
        title="SKU a pérdida con ad spend",
        color="#f43f5e",              # red
        fields=[
            {"title": "SKU", "value": sku, "short": True},
            {"title": "Margin %", "value": f"{margin_pct:.1f}%", "short": True},
            {"title": "Ad spend 3d", "value": f"${ad_spend_3d:.0f}", "short": True},
        ],
    )