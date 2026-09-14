"""Mock LLM — decisiones determinísticas basadas en reglas, sin API key.

Útil para:
- Desarrollo local sin gastar créditos
- Tests automatizados
- Demos
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm_providers.base import (
    LLMClient,
    LLMError,
    LLMMessage,
    LLMResponse,
)


SYSTEM = """Eres el CFO de un ecommerce. Tu ÚNICA métrica es el margen neto por SKU.

Reglas:
1. Si margen_pct <= 0 Y ad_spend_3d > 20 → action=pause_ads
2. Si margen_pct > 30 Y stock > 20 → action=scale_budget (+20%)
3. Si 0 < margen_pct <= 15 → action=increase_price (+10%)
4. Si 15 < margen_pct <= 30 → action=scale_budget (+10%, conservador)
5. Nunca ejecutes directo. Solo emite una pending_action.

Responde SOLO JSON:
{
  "action": "...",
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "whatsapp_message": "...",
  "payload": {"...": "..."}
}
"""


class MockLLM(LLMClient):
    """Deterministic LLM based on heuristics. No external calls."""

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Extract user message (last one)
        user_msg = next(
            (m for m in reversed(messages) if m.role == "user"), None
        )
        if not user_msg:
            raise LLMError("No user message")

        # Parse SKU data
        data = self._parse_context(user_msg.content)
        decision = self._decide(data)

        return LLMResponse(
            content=json.dumps(decision, ensure_ascii=False),
            model="mock-llm-v1",
            usage={"input": len(user_msg.content), "output": 100},
            raw={"decision": decision, "mocked": True},
        )

    async def health(self) -> bool:
        return True

    @staticmethod
    def _parse_context(text: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for line in text.split("\n"):
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if k == "SKU":
                out["sku"] = v
            elif k == "Estado":
                out["state"] = v
            elif k == "Margen neto %":
                try:
                    out["margin_pct"] = float(v)
                except ValueError:
                    pass
            elif k == "Ad spend 3d":
                try:
                    out["ad_spend_3d"] = float(v)
                except ValueError:
                    pass
            elif k == "Stock":
                try:
                    out["stock"] = int(v)
                except ValueError:
                    pass
            elif k == "Revenue 30d":
                try:
                    out["revenue_30d"] = float(v)
                except ValueError:
                    pass
        return out

    @staticmethod
    def _decide(data: dict) -> dict:
        sku = data.get("sku", "?")
        margin = data.get("margin_pct", 0)
        ad_3d = data.get("ad_spend_3d", 0)
        stock = data.get("stock", 0)
        revenue = data.get("revenue_30d", 0)

        # Regla 1: A pérdida con ad spend
        if margin <= 0 and ad_3d > 20:
            return {
                "action": "pause_ads",
                "confidence": 0.95,
                "reasoning": (
                    f"SKU a pérdida ({margin:.1f}%) con ${ad_3d:.0f} en ads "
                    f"últimos 3 días. ROAS implícito < 1."
                ),
                "whatsapp_message": (
                    f"🚨 *{sku}* lleva 3 días a pérdida ({margin:.1f}%) "
                    f"con ${ad_3d:.0f} en ads.\n"
                    f"¿Pauso la campaña? Responde *SI* para ejecutar."
                ),
                "payload": {"reason": "negative_margin_3d"},
            }

        # Regla 2: Ganador con stock
        if margin > 30 and stock > 20:
            return {
                "action": "scale_budget",
                "confidence": 0.85,
                "reasoning": (
                    f"SKU ganador ({margin:.1f}%) con stock "
                    f"abundante ({stock})."
                ),
                "whatsapp_message": (
                    f"✅ *{sku}* es ganador ({margin:.1f}% margen, "
                    f"stock {stock}).\n¿Subo presupuesto +20%? *SI*"
                ),
                "payload": {"new_budget_pct": 20},
            }

        # Regla 4: A optimizar conservador
        if 15 < margin <= 30:
            return {
                "action": "scale_budget",
                "confidence": 0.7,
                "reasoning": f"SKU a optimizar ({margin:.1f}%). Escala moderada.",
                "whatsapp_message": (
                    f"📈 *{sku}* tiene margen {margin:.1f}% — está OK pero "
                    f"puede mejorar.\n¿Subo presupuesto +10%? *SI*"
                ),
                "payload": {"new_budget_pct": 10},
            }

        # Regla 3: En riesgo
        if 0 < margin <= 15:
            return {
                "action": "increase_price",
                "confidence": 0.75,
                "reasoning": (
                    f"SKU en riesgo ({margin:.1f}%). Subir precio "
                    f"10% lo lleva a ~{margin * 1.18:.1f}%."
                ),
                "whatsapp_message": (
                    f"⚠️ *{sku}* está en riesgo ({margin:.1f}% margen, "
                    f"revenue ${revenue:.0f}).\n"
                    f"¿Subo precio 10%? *SI*"
                ),
                "payload": {"new_price_pct": 10},
            }

        return {
            "action": "none",
            "confidence": 0.0,
            "reasoning": "Sin acción requerida.",
            "whatsapp_message": "",
            "payload": {},
        }