"""Tenant schemas."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TenantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source: Literal["shopify", "woocommerce"]
    credentials: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    locale: Literal["es", "en"] = "es"


class TenantOut(BaseModel):
    id: UUID
    name: str
    source: str
    locale: str
    active: bool
    created_at: datetime