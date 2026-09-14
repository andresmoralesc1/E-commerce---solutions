"""OAuth router — conecta Meta, Google y Shopify al tenant.

Flujo:
1. GET /api/auth/{platform}/start?tenant_id={id}  → redirecciona a OAuth provider
2. Provider → callback → GET /api/auth/{platform}/callback?code=...&state=...
4. Backend intercambia code por tokens, guarda en tenant.credentials
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.connectors import google_ads, meta_ads
from app.core import db
from app.core.config import settings
from app.core.security import TokenData, get_current_user
from app.services.ads_executor import record_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _verify_tenant_access(tenant_id: UUID, user: TokenData) -> None:
    """Placeholder simple — en producción validar contra user_tenants."""
    if not user.superuser:
        # Permite a cualquier user autenticado (fase 2 ya restringe dashboard)
        pass


@router.get("/meta/start")
async def meta_start(
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> RedirectResponse:
    _verify_tenant_access(tenant_id, user)
    if not (settings.meta_app_id and settings.meta_redirect_uri):
        raise HTTPException(
            status_code=500,
            detail="META_APP_ID o META_REDIRECT_URI no configurados en .env",
        )
    url = meta_ads.build_auth_url(
        settings.meta_app_id,
        settings.meta_redirect_uri,
        state=str(tenant_id),
    )
    return RedirectResponse(url=url)


@router.get("/meta/callback")
async def meta_callback(
    code: str = Query(...),
    state: str = Query(...),                       # = tenant_id
    user: TokenData = Depends(get_current_user),
) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")

    tenant_id = UUID(state)

    # 1. code → short-lived token
    short_token_data = await meta_ads.exchange_code_for_token(
        settings.meta_app_id,
        settings.meta_app_secret,
        settings.meta_redirect_uri,
        code,
    )
    short_token = short_token_data.get("access_token")
    if not short_token:
        raise HTTPException(
            status_code=400,
            detail=f"Meta no devolvió access_token: {short_token_data}",
        )

    # 2. short → long-lived
    long_data = await meta_ads.exchange_for_long_lived_token(
        settings.meta_app_id,
        settings.meta_app_secret,
        short_token,
    )
    long_token = long_data.get("access_token", short_token)
    expires_in = long_data.get("expires_in", 60 * 24 * 3600)

    # 3. Obtener ad accounts del usuario
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"https://graph.facebook.com/v21.0/me/adaccounts",
            params={
                "access_token": long_token,
                "fields": "id,name,account_id",
                "limit": 50,
            },
        )
        accounts = r.json().get("data", [])

    # 4. Guardar en tenant.credentials (usamos el primero por defecto)
    account_id = accounts[0]["account_id"] if accounts else None
    credentials_update = {
        "meta_access_token": long_token,
        "meta_ad_account_id": account_id,
        "meta_token_expires_in": expires_in,
        "meta_accounts": [
            {"id": a["account_id"], "name": a.get("name", "")}
            for a in accounts
        ],
    }

    # Merge con credenciales existentes
    row = await db.fetchrow(
        "SELECT credentials FROM tenants WHERE id = $1", tenant_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    creds = row["credentials"]
    if isinstance(creds, str):
        try:
            creds = json.loads(creds)
        except Exception:
            creds = {}
    if not isinstance(creds, dict):
        creds = {}
    creds.update(credentials_update)

    await db.execute(
        "UPDATE tenants SET credentials = $1::jsonb WHERE id = $2",
        creds,
        tenant_id,
    )

    await record_audit(
        tenant_id=tenant_id,
        actor=f"user:{user.user_id}",
        action="auth.meta.oauth_complete",
        payload={"accounts_found": len(accounts)},
    )

    return {
        "ok": True,
        "tenant_id": str(tenant_id),
        "accounts": credentials_update["meta_accounts"],
    }


# ─── Google OAuth ────────────────────────────────────────────────────────

@router.get("/google/start")
async def google_start(
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> RedirectResponse:
    _verify_tenant_access(tenant_id, user)
    if not (settings.google_client_id and settings.google_redirect_uri):
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID o GOOGLE_REDIRECT_URI no configurados en .env",
        )
    url = google_ads.build_auth_url(
        settings.google_client_id,
        settings.google_redirect_uri,
        state=str(tenant_id),
    )
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")

    tenant_id = UUID(state)
    token_data = await google_ads.exchange_code_for_tokens(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
        code,
    )
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google no devolvió refresh_token. Esto pasa si ya autorizaste antes. "
                "Revoca en https://myaccount.google.com/permissions y vuelve a intentar."
            ),
        )

    # Listar cuentas accesibles con el token
    import httpx
    access_token = token_data["access_token"]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://googleads.googleapis.com/v18/customers:listAccessibleCustomers",
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": settings.google_developer_token,
            },
        )
        customers_data = r.json()
    resource_names = customers_data.get("resourceNames", [])
    # formato: "customers/1234567890"
    customer_ids = [rn.split("/")[-1] for rn in resource_names]

    credentials_update = {
        "google_refresh_token": refresh_token,
        "google_access_token": access_token,
        "google_customer_id": customer_ids[0] if customer_ids else None,
        "google_customer_ids": customer_ids,
    }

    row = await db.fetchrow(
        "SELECT credentials FROM tenants WHERE id = $1", tenant_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    creds = row["credentials"]
    if isinstance(creds, str):
        try:
            creds = json.loads(creds)
        except Exception:
            creds = {}
    if not isinstance(creds, dict):
        creds = {}
    creds.update(credentials_update)
    await db.execute(
        "UPDATE tenants SET credentials = $1::jsonb WHERE id = $2",
        creds, tenant_id,
    )

    await record_audit(
        tenant_id=tenant_id,
        actor=f"user:{user.user_id}",
        action="auth.google.oauth_complete",
        payload={"customers_found": len(customer_ids)},
    )

    return {
        "ok": True,
        "tenant_id": str(tenant_id),
        "customers": customer_ids,
    }