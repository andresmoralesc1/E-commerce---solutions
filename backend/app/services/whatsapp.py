"""WhatsApp service — envío de mensajes vía Evolution API.

Soporta:
- Real send via Evolution API v2
- Dry-run/stub mode cuando Evolution no está conectado
- Multi-instancia (cada tenant puede tener su propia instancia Evolution)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from app.core import db
from app.core.config import settings
from app.core.logging import log


@dataclass
class SendResult:
    ok: bool
    mode: str                # "evolution" | "stub" | "dry_run"
    provider_response: dict | None = None
    error: str | None = None


async def _tenant_manager_phone(tenant_id: UUID) -> str | None:
    """Lee el WhatsApp del manager del tenant desde settings."""
    row = await db.fetchrow(
        "SELECT settings FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row:
        return None
    settings = row["settings"]
    if isinstance(settings, str):
        import json as _json
        try:
            settings = _json.loads(settings)
        except Exception:
            return None
    if isinstance(settings, dict):
        return settings.get("manager_phone")
    return None


async def _tenant_evolution_instance(tenant_id: UUID) -> str | None:
    """Lee el instance_name de Evolution para el tenant."""
    row = await db.fetchrow(
        "SELECT settings FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not row:
        return None
    settings = row["settings"]
    if isinstance(settings, str):
        import json as _json
        try:
            settings = _json.loads(settings)
        except Exception:
            return None
    if isinstance(settings, dict):
        return settings.get("evolution_instance")
    return None


async def send_text(
    tenant_id: UUID,
    text: str,
    phone: str | None = None,
    instance_name: str | None = None,
) -> SendResult:
    """Envía un mensaje de texto vía Evolution. Si Evolution no responde,
    fallback a stub que solo registra en logs.
    """
    phone = phone or await _tenant_manager_phone(tenant_id)
    if not phone:
        return SendResult(
            ok=False,
            mode="stub",
            error="tenant sin manager_phone configurado en settings",
        )
    instance = instance_name or await _tenant_evolution_instance(tenant_id) or "brain"

    base = settings.evolution_api_url
    if not base:
        return SendResult(
            ok=False,
            mode="stub",
            error="EVOLUTION_API_URL no configurada",
        )

    url = f"{base}/message/sendText/{instance}"
    payload = {
        "number": phone,
        "text": text,
    }
    headers = {"apikey": settings.evolution_api_key}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code in (200, 201):
            return SendResult(
                ok=True,
                mode="evolution",
                provider_response=r.json(),
            )
        return SendResult(
            ok=False,
            mode="evolution",
            error=f"Evolution API {r.status_code}: {r.text[:300]}",
        )
    except httpx.HTTPError as e:
        log.warning("whatsapp.evolution_unreachable", error=str(e))
        return SendResult(
            ok=False,
            mode="stub",
            error=f"evolution unreachable: {e}; logged only",
        )
    except Exception as e:
        return SendResult(
            ok=False,
            mode="stub",
            error=str(e),
        )


async def send_pending_action_message(action_id: UUID) -> SendResult:
    """Envía el whatsapp_message del pending_action al manager del tenant."""
    from app.core import db
    row = await db.fetchrow(
        "SELECT tenant_id, whatsapp_message FROM pending_actions WHERE id = $1",
        action_id,
    )
    if not row:
        return SendResult(ok=False, mode="stub", error="action_not_found")
    if not row["whatsapp_message"]:
        return SendResult(ok=False, mode="stub", error="no whatsapp_message")

    result = await send_text(row["tenant_id"], row["whatsapp_message"])
    log.info(
        "whatsapp.send",
        action_id=str(action_id),
        ok=result.ok,
        mode=result.mode,
        error=result.error,
    )
    return result