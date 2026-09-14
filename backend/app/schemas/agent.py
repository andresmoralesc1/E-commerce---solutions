"""Agent decision schemas."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DecideIn(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    tenant_id: UUID
    lookback_days: int = Field(default=3, ge=1, le=90)


class DecideOut(BaseModel):
    action_id: UUID
    sku: str
    action: str
    confidence: float
    reasoning: str
    whatsapp_message: str
    payload: dict[str, Any]


class ConfirmIn(BaseModel):
    approved: bool
    response_text: str | None = None


class PendingActionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    sku: str | None
    action_type: str
    status: str
    reasoning: str | None
    whatsapp_message: str | None
    confidence: float | None
    created_at: datetime
    expires_at: datetime
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    execution_result: dict[str, Any] | None = None