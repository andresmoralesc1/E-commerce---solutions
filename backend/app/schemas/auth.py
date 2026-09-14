"""Auth + user schemas."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    superuser: bool
    tenant_ids: list[UUID] = []


class BootstrapIn(BaseModel):
    """Primer superuser del sistema (solo si users está vacío)."""
    email: EmailStr
    password: str = Field(min_length=12)
    full_name: str | None = None