"""Agent decision service — orquesta LLM + reglas deterministas."""
import json
import re
from dataclasses import dataclass
from uuid import UUID

from app.core.llm_providers import LLMMessage, get_llm_client
from app.core.logging import log
from app.services.classifier import SKUState
from app.services.profitability import get_sku


SYSTEM_PROMPT = """Eres el CFO y Media Buyer de un ecommerce.
Tu ÚNICA métrica es el margen neto real por SKU (no ROAS, no revenue).

Reglas inquebrantables:
1. Si SKU está A_PERDIDA y ad_spend_3d > 20 (en moneda local) →
   recomienda action=pause_ads.
2. Si SKU está GANADOR y stock > 20 → action=scale_budget (+20%).
3. Si SKU está EN_RIESGO → action=increase_price (+10%) o renegotiate_cogs.
4. Si SKU está A_OPTIMIZAR → action=scale_budget (+10%) con caution.
5. NUNCA ejecutes. Tu salida SIEMPRE va a una cola de pending_actions
   que requiere confirmación humana (WhatsApp).

Debes responder SOLO en JSON válido con esta estructura:
{
  "action": "pause_ads" | "scale_budget" | "increase_price" | "renegotiate_cogs" | "none",
  "confidence": 0.0-1.0,
  "reasoning": "explicación corta y concreta en 2 líneas",
  "whatsapp_message": "mensaje para el dueño con emoji, máx 280 chars",
  "payload": {
    "campaign_id": "...",
    "new_budget_pct": 20,
    "new_price_pct": 10
  }
}

Si NO hay acción recomendada (margen estable, sin alertas), action=none,
confidence=0, whatsapp_message="".
"""


@dataclass
class AgentDecision:
    action: str
    confidence: float
    reasoning: str
    whatsapp_message: str
    payload: dict


def _parse_llm_json(content: str) -> dict:
    """Extrae JSON de la respuesta del LLM (a veces viene con markdown)."""
    # strip ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # primer { ... } balanceado
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(content[start : end + 1])
    raise ValueError(f"LLM no devolvió JSON: {content[:200]}")


async def decide_for_sku(tenant_id: UUID, sku: str) -> AgentDecision:
    """Decisión del agente para un SKU concreto."""
    sk = await get_sku(tenant_id, sku)
    if not sk:
        return AgentDecision(
            action="none",
            confidence=0,
            reasoning="SKU no encontrado",
            whatsapp_message="",
            payload={},
        )

    # Override determinista: si la regla es obvia, no preguntamos al LLM
    state = sk["state"]
    if state == SKUState.A_PERDIDA.value and float(sk["ad_spend_3d"] or 0) > 20:
        return AgentDecision(
            action="pause_ads",
            confidence=0.95,
            reasoning=(
                f"SKU a pérdida ({sk['net_margin_pct']:.1f}%) con "
                f"{sk['ad_spend_3d']:.0f} en ads en últimos 3 días"
            ),
            whatsapp_message=(
                f"🚨 *{sku}* lleva 3 días a pérdida ({sk['net_margin_pct']:.1f}%) "
                f"con ${sk['ad_spend_3d']:.0f} en ads.\n"
                f"¿Pauso la campaña? Responde *SI* para ejecutar."
            ),
            payload={
                "campaign_id": sk.get("campaign_id"),
                "reason": "negative_margin_3d",
            },
        )

    if state == SKUState.GANADOR.value and (sk["stock"] or 0) > 20:
        return AgentDecision(
            action="scale_budget",
            confidence=0.85,
            reasoning=(
                f"SKU ganador ({sk['net_margin_pct']:.1f}%) con stock "
                f"abundante ({sk['stock']})"
            ),
            whatsapp_message=(
                f"✅ *{sku}* es ganador ({sk['net_margin_pct']:.1f}% margen, "
                f"stock {sk['stock']}).\n¿Subo presupuesto +20%? *SI*"
            ),
            payload={"new_budget_pct": 20},
        )

    if state == SKUState.EN_RIESGO.value:
        # LLM decide entre precio y renegociar cogs
        pass

    # Para el resto, pedimos al LLM con contexto estructurado
    context = (
        f"SKU: {sku}\n"
        f"Título: {sk.get('title','')}\n"
        f"Estado: {state}\n"
        f"Margen neto %: {sk['net_margin_pct']:.2f}\n"
        f"Margen neto absoluto: {sk['net_margin_abs']:.2f}\n"
        f"Revenue 30d: {sk['revenue_30d']:.2f}\n"
        f"COGS: {sk['cogs_total']:.2f}\n"
        f"Ad spend 30d: {sk['ad_spend_total']:.2f}\n"
        f"Ad spend 3d: {sk['ad_spend_3d']:.2f}\n"
        f"Stock: {sk['stock']}\n"
        f"Unidades vendidas: {sk['units_sold']}\n"
    )

    client = get_llm_client()
    try:
        resp = await client.complete(
            [
                LLMMessage("system", SYSTEM_PROMPT),
                LLMMessage("user", context),
            ],
            temperature=0.2,
            max_tokens=600,
            json_mode=True,
        )
        data = _parse_llm_json(resp.content)
        return AgentDecision(
            action=data.get("action", "none"),
            confidence=float(data.get("confidence", 0)),
            reasoning=data.get("reasoning", ""),
            whatsapp_message=data.get("whatsapp_message", ""),
            payload=data.get("payload", {}),
        )
    except Exception as e:
        log.warning("agent.llm_failed", sku=sku, error=str(e))
        return AgentDecision(
            action="none",
            confidence=0,
            reasoning=f"LLM error: {e}",
            whatsapp_message="",
            payload={},
        )


async def queue_action(
    tenant_id: UUID,
    sku: str,
    decision: AgentDecision,
) -> dict:
    """Inserta una acción pendiente en DB para confirmación humana."""
    from app.core import db

    if decision.action == "none":
        return None

    row = await db.fetchrow(
        """
        INSERT INTO pending_actions
          (tenant_id, sku, action_type, payload, whatsapp_message,
           reasoning, confidence)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        RETURNING id, created_at
        """,
        tenant_id,
        sku,
        decision.action,
        json.dumps(decision.payload),
        decision.whatsapp_message,
        decision.reasoning,
        decision.confidence,
    )
    return dict(row)


async def confirm_and_execute(action_id: str, approved: bool) -> dict:
    """Confirma (o rechaza) y, si aprobada, ejecuta."""
    from app.core import db

    pa = await db.fetchrow(
        "SELECT * FROM pending_actions WHERE id = $1",
        action_id,
    )
    if not pa:
        return {"ok": False, "error": "action_not_found"}
    pa = dict(pa)

    # payload viene como string desde jsonb — deserializar
    if isinstance(pa.get("payload"), str):
        try:
            pa["payload"] = json.loads(pa["payload"])
        except Exception:
            pa["payload"] = {}

    if pa["status"] != "pending":
        return {"ok": False, "error": f"already_{pa['status']}"}

    if not approved:
        await db.execute(
            """
            UPDATE pending_actions
            SET status='rejected', approved_at=NOW(),
                response_text=$1
            WHERE id=$2
            """,
            "rejected_by_user",
            action_id,
        )
        return {"ok": True, "status": "rejected"}

    await db.execute(
        """
        UPDATE pending_actions
        SET status='approved', approved_at=NOW()
        WHERE id=$1
        """,
        action_id,
    )

    # Ejecutar (Fase 3+ — placeholder fase 1)
    try:
        from app.services.ads_executor import execute_action

        result = await execute_action(pa["tenant_id"], pa)
        await db.execute(
            """
            UPDATE pending_actions
            SET status='executed', executed_at=NOW(),
                execution_result=$1
            WHERE id=$2
            """,
            json.dumps(result),
            action_id,
        )
        return {"ok": True, "status": "executed", "result": result}
    except Exception as e:
        log.error("agent.execute_failed", action_id=action_id, error=str(e))
        await db.execute(
            """
            UPDATE pending_actions
            SET status='failed', executed_at=NOW(),
                execution_result=$1
            WHERE id=$2
            """,
            json.dumps({"error": str(e)}),
            action_id,
        )
        return {"ok": False, "status": "failed", "error": str(e)}