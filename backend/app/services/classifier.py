"""SKU classifier — Ganador / A Optimizar / En Riesgo / A Pérdida."""
from enum import Enum


class SKUState(str, Enum):
    GANADOR = "GANADOR"
    A_OPTIMIZAR = "A_OPTIMIZAR"
    EN_RIESGO = "EN_RIESGO"
    A_PERDIDA = "A_PERDIDA"


def classify(net_margin_pct: float | None) -> SKUState:
    """Clasifica un SKU según su porcentaje de margen neto.

    Reglas (alineadas con init.sql::classify_sku):
      > 30% → GANADOR
      > 15% → A_OPTIMIZAR
      > 0%  → EN_RIESGO
      ≤ 0%  → A_PERDIDA
    """
    if net_margin_pct is None:
        return SKUState.A_OPTIMIZAR
    if net_margin_pct > 30:
        return SKUState.GANADOR
    if net_margin_pct > 15:
        return SKUState.A_OPTIMIZAR
    if net_margin_pct > 0:
        return SKUState.EN_RIESGO
    return SKUState.A_PERDIDA


def state_color(state: SKUState | str) -> str:
    """Devuelve un color CSS legible para el semáforo."""
    s = state.value if isinstance(state, SKUState) else state
    return {
        SKUState.GANADOR.value: "green",
        SKUState.A_OPTIMIZAR.value: "yellow",
        SKUState.EN_RIESGO.value: "orange",
        SKUState.A_PERDIDA.value: "red",
    }.get(s, "gray")