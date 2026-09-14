"""JWT auth helpers + FastAPI dependency."""
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


class TokenData(BaseModel):
    user_id: UUID
    email: str
    superuser: bool = False


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: UUID, email: str, superuser: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "email": email,
        "superuser": superuser,
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenData:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        email = payload.get("email")
        if user_id is None or email is None:
            raise cred_exc
        return TokenData(
            user_id=UUID(user_id),
            email=email,
            superuser=payload.get("superuser", False),
        )
    except (JWTError, ValueError):
        raise cred_exc


async def get_tenant_ids(user: TokenData) -> list[UUID]:
    """Devuelve los tenants a los que el user tiene acceso."""
    from app.core import db

    rows = await db.fetch(
        "SELECT tenant_id FROM user_tenants WHERE user_id = $1",
        user.user_id,
    )
    if user.superuser and not rows:
        # superuser sin tenants asignados ve todos
        all_rows = await db.fetch("SELECT id FROM tenants WHERE active = TRUE")
        return [r["id"] for r in all_rows]
    return [r["tenant_id"] for r in rows]