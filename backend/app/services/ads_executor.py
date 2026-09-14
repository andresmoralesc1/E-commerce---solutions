"""Ads executor — pausa/sube campañas en Meta y Google.

Fase 1: stubs que registran el resultado. Se completan en Fase 3
cuando los tokens de Meta/Google estén autorizados.
"""
from typing import Any
from uuid import UUID


async def execute_action(tenant_id: UUID, action: dict) -> dict[str, Any]:
    """Ejecuta la acción aprobada sobre la plataforma de ads correcta."""
    action_type = action["action_type"]
    payload = action.get("payload") or {}

    if action_type == "pause_ads":
        return await _pause_campaign(tenant_id, payload)
    if action_type == "scale_budget":
        return await _scale_budget(tenant_id, payload)
    if action_type == "increase_price":
        return await _increase_price(tenant_id, payload)
    if action_type == "renegotiate_cogs":
        return {"status": "noted", "note": "negociación manual con proveedor"}

    return {"status": "unknown_action", "action_type": action_type}


async def _pause_campaign(tenant_id: UUID, payload: dict) -> dict:
    campaign_id = payload.get("campaign_id")
    # TODO Fase 3: detectar plataforma y llamar a Meta/Google API
    return {
        "status": "stub_phase_1",
        "would_pause": campaign_id,
        "note": "Implementar en Fase 3 — Meta/Google SDK integration",
    }


async def _scale_budget(tenant_id: UUID, payload: dict) -> dict:
    return {
        "status": "stub_phase_1",
        "would_scale": payload.get("new_budget_pct"),
    }


async def _increase_price(tenant_id: UUID, payload: dict) -> dict:
    sku = payload.get("sku")
    pct = payload.get("new_price_pct")
    return {
        "status": "stub_phase_1",
        "would_increase": {"sku": sku, "pct": pct},
    }