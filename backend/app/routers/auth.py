"""Auth router — login + bootstrap first user."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core import db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    get_tenant_ids,
    hash_password,
    verify_password,
    TokenData,
)
from app.schemas.auth import BootstrapIn, TokenOut, UserOut

router = APIRouter(prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenOut:
    row = await db.fetchrow(
        "SELECT id, email, password_hash, superuser, active FROM users WHERE email = $1",
        form.username,
    )
    if not row or not row["active"] or not verify_password(
        form.password, row["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(row["id"], row["email"], row["superuser"])
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.post("/bootstrap", response_model=TokenOut, status_code=201)
async def bootstrap_first_user(body: BootstrapIn) -> TokenOut:
    """Crea el primer superuser SOLO si users está vacío."""
    exists = await db.fetchval("SELECT COUNT(*) FROM users")
    if exists and exists > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap solo permitido con users vacío",
        )
    user_id = await db.fetchval(
        """
        INSERT INTO users (email, password_hash, full_name, superuser)
        VALUES ($1, $2, $3, TRUE)
        RETURNING id
        """,
        body.email,
        hash_password(body.password),
        body.full_name,
    )
    token = create_access_token(user_id, body.email, True)
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserOut)
async def me(user: TokenData = Depends(get_current_user)) -> UserOut:
    tids = await get_tenant_ids(user)
    return UserOut(
        id=user.user_id,
        email=user.email,
        full_name=None,
        superuser=user.superuser,
        tenant_ids=tids,
    )