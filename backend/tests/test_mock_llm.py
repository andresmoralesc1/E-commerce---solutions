"""Tests unitarios para MockLLM."""
import pytest

from app.core.llm_providers.mock import MockLLM
from app.core.llm_providers.base import LLMMessage


def make_ctx(**kwargs) -> str:
    defaults = {
        "SKU": "TEST-001",
        "Estado": "EN_RIESGO",
        "Margen neto %": "5.0",
        "Ad spend 3d": "500",
        "Stock": "50",
        "Revenue 30d": "1000000",
    }
    defaults.update(kwargs)
    return "\n".join(f"{k}: {v}" for k, v in defaults.items())


@pytest.fixture
def llm() -> MockLLM:
    return MockLLM()


@pytest.mark.asyncio
async def test_health(llm):
    assert await llm.health() is True


@pytest.mark.asyncio
async def test_pause_ads_decision(llm):
    messages = [LLMMessage("user", make_ctx(
        SKU="PROD-A",
        **{"Margen neto %": "-15.0", "Ad spend 3d": "1500"},
    ))]
    resp = await llm.complete(messages, json_mode=True)
    import json
    data = json.loads(resp.content)
    assert data["action"] == "pause_ads"
    assert data["confidence"] >= 0.9
    assert "SI" in data["whatsapp_message"]


@pytest.mark.asyncio
async def test_scale_budget_decision(llm):
    messages = [LLMMessage("user", make_ctx(
        SKU="PROD-B",
        **{"Margen neto %": "45.0", "Stock": "100"},
    ))]
    resp = await llm.complete(messages, json_mode=True)
    import json
    data = json.loads(resp.content)
    assert data["action"] == "scale_budget"
    assert data["payload"]["new_budget_pct"] == 20


@pytest.mark.asyncio
async def test_increase_price_decision(llm):
    messages = [LLMMessage("user", make_ctx(
        SKU="PROD-C",
        **{"Margen neto %": "8.0", "Stock": "10"},
    ))]
    resp = await llm.complete(messages, json_mode=True)
    import json
    data = json.loads(resp.content)
    assert data["action"] == "increase_price"
    assert data["payload"]["new_price_pct"] == 10


@pytest.mark.asyncio
async def test_no_action_needed(llm):
    messages = [LLMMessage("user", make_ctx(
        SKU="PROD-D",
        **{"Margen neto %": "20.0"},     # A_OPTIMIZAR
    ))]
    resp = await llm.complete(messages, json_mode=True)
    import json
    data = json.loads(resp.content)
    # A_OPTIMIZAR (15-30%) → scale_budget conservador
    assert data["action"] == "scale_budget"
    assert data["payload"]["new_budget_pct"] == 10