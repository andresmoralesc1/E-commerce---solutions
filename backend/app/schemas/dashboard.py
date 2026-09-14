"""Dashboard schemas."""
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ProfitabilityRow(BaseModel):
    product_id: int
    tenant_id: UUID
    sku: str
    title: str | None
    stock: int
    revenue_30d: float
    cogs_total: float
    shipping_total: float
    gateway_fee_total: float
    ad_spend_total: float
    ad_spend_3d: float
    net_margin_abs: float
    net_margin_pct: float
    roas_real: float | None
    state: str


class KPIsOut(BaseModel):
    revenue_total: float
    net_margin_total: float
    ad_spend_total: float
    cogs_total: float
    sku_total: int
    skus_burning: int
    money_burned_3d: float