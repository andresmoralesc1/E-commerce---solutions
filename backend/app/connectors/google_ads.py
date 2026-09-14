"""Google Ads API connector — implementación completa Fase 3.

Requiere en tenant.credentials:
- google_refresh_token: refresh token OAuth2
- google_customer_id: '1234567890' (sin guiones)
- google_developer_token: (alternativamente en .env del backend)

Opcional en .env:
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DEVELOPER_TOKEN
"""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import httpx

from app.core import db
from app.core.logging import log

GOOGLE_ADS_API_VERSION = "v18"
BASE_URL = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"


class GoogleAdsAPIError(Exception):
    pass


# ─── OAuth flow ──────────────────────────────────────────────────────────

def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str = "ecommerce-brain",
) -> str:
    return (
        "https://accounts.google.com/o/oauth2/v2/auth"
        "?access_type=offline"
        "&prompt=consent"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=https://www.googleapis.com/auth/adwords"
        f"&state={state}"
    )


async def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict[str, Any]:
    """Intercambia code por access_token + refresh_token."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if r.status_code != 200:
            raise GoogleAdsAPIError(
                f"Token exchange failed: {r.status_code} {r.text[:300]}"
            )
        return r.json()


async def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Renueva access_token desde refresh_token."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if r.status_code != 200:
            raise GoogleAdsAPIError(f"Token refresh failed: {r.text[:300]}")
        return r.json()


# ─── Campaign actions ────────────────────────────────────────────────────

def _headers(access_token: str, developer_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "developer-token": developer_token,
        "Content-Type": "application/json",
        "login-customer-id": "",
    }


async def _ensure_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> str:
    """Devuelve un access_token fresco (refresca si hace falta)."""
    data = await refresh_access_token(client_id, client_secret, refresh_token)
    return data["access_token"]


async def pause_campaign(
    customer_id: str,
    access_token: str,
    developer_token: str,
    campaign_id: str,
) -> dict[str, Any]:
    """Pausa una campaña (CampaignStatus.PAUSED)."""
    query = f"""
        SELECT campaign.id, campaign.name, campaign.status
        FROM campaign
        WHERE campaign.id = {int(campaign_id)}
    """
    mutate = """
        {
          "operations": [{
            "update": {
              "resourceName": "customers/%s/campaigns/%s",
              "status": "PAUSED"
            },
            "updateMask": "status"
          }]
        }
    """ % (customer_id, campaign_id)
    async with httpx.AsyncClient(timeout=30) as client:
        headers = _headers(access_token, developer_token)
        headers["login-customer-id"] = customer_id
        r = await client.post(
            f"{BASE_URL}/customers/{customer_id}/campaigns:mutate",
            headers=headers,
            content=mutate,
        )
        if r.status_code not in (200, 201):
            raise GoogleAdsAPIError(
                f"Pause campaign failed: {r.status_code} {r.text[:300]}"
            )
        return r.json()


async def update_campaign_budget(
    customer_id: str,
    access_token: str,
    developer_token: str,
    campaign_id: str,
    new_budget_micros: int,
) -> dict[str, Any]:
    """Actualiza el daily_budget de un campaign budget resource."""
    # Primero: obtener el resource name del campaign budget asociado
    query = f"""
        SELECT campaign.id, campaign.name, campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = {int(campaign_id)}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        headers = _headers(access_token, developer_token)
        headers["login-customer-id"] = customer_id
        r = await client.post(
            f"{BASE_URL}/customers/{customer_id}/googleAds:search",
            headers=headers,
            json={"query": query},
        )
        if r.status_code != 200:
            raise GoogleAdsAPIError(f"Get campaign failed: {r.text[:300]}")
        rows = r.json()
        if not rows:
            raise GoogleAdsAPIError("Campaign not found")
        budget_resource = rows[0]["campaign"]["campaignBudget"]
        budget_id = budget_resource.split("/")[-1]

        mutate = (
            '{"operations":[{"update":{'
            f'"resourceName":"customers/{customer_id}/campaignBudgets/{budget_id}",'
            f'"amountMicros":"{new_budget_micros}"'
            '},"updateMask":"amount_micros"}]}'
        )
        r2 = await client.post(
            f"{BASE_URL}/customers/{customer_id}/campaignBudgets:mutate",
            headers=headers,
            content=mutate,
        )
        if r2.status_code not in (200, 201):
            raise GoogleAdsAPIError(
                f"Update budget failed: {r2.status_code} {r2.text[:300]}"
            )
        return r2.json()


async def scale_campaign_budget(
    customer_id: str,
    access_token: str,
    developer_token: str,
    campaign_id: str,
    pct_increase: int,
) -> dict[str, Any]:
    """Lee el budget actual y lo escala por pct_increase."""
    current = await get_campaign(customer_id, access_token, developer_token, campaign_id)
    budget_micros = int(current.get("campaignBudget", {}).get("amountMicros", 0))
    new_budget = int(budget_micros * (1 + pct_increase / 100))
    return await update_campaign_budget(
        customer_id, access_token, developer_token, campaign_id, new_budget
    )


async def get_campaign(
    customer_id: str,
    access_token: str,
    developer_token: str,
    campaign_id: str,
) -> dict[str, Any]:
    query = f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = {int(campaign_id)}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        headers = _headers(access_token, developer_token)
        headers["login-customer-id"] = customer_id
        r = await client.post(
            f"{BASE_URL}/customers/{customer_id}/googleAds:search",
            headers=headers,
            json={"query": query},
        )
        if r.status_code != 200:
            raise GoogleAdsAPIError(f"Get campaign failed: {r.text[:300]}")
        rows = r.json()
        return rows[0]["campaign"] if rows else {}


# ─── Spend pull ──────────────────────────────────────────────────────────

async def fetch_ad_spend(
    tenant_id: UUID,
    refresh_token: str,
    customer_id: str,
    since: date,
    until: date,
    client_id: str = "",
    client_secret: str = "",
    developer_token: str = "",
) -> int:
    """Pull ad spend del customer, sin breakdown UTM (lo hace attribution proporcional).

    GAQL:
      SELECT campaign.id, campaign.name, segments.date, metrics.cost_micros,
              metrics.impressions, metrics.clicks
      FROM campaign
      WHERE segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
    """
    if not (client_id and client_secret and developer_token):
        raise GoogleAdsAPIError(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DEVELOPER_TOKEN required"
        )

    access_token = await _ensure_access_token(client_id, client_secret, refresh_token)
    query = f"""
        SELECT
          campaign.id, campaign.name,
          segments.date,
          metrics.cost_micros, metrics.impressions, metrics.clicks,
          metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{since.isoformat()}' AND '{until.isoformat()}'
        AND campaign.status != 'REMOVED'
    """
    headers = _headers(access_token, developer_token)
    headers["login-customer-id"] = customer_id

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/customers/{customer_id}/googleAds:search",
            headers=headers,
            json={"query": query, "pageSize": 1000},
        )
        if r.status_code != 200:
            log.warning(
                "google.api_error",
                status=r.status_code,
                body=r.text[:200],
            )
            return 0
        data = r.json()

    inserted = 0
    for row in data.get("results", []):
        c = row.get("campaign", {})
        seg = row.get("segments", {})
        m = row.get("metrics", {})
        try:
            d = date.fromisoformat(seg["date"])
        except Exception:
            continue
        await db.execute(
            """
            INSERT INTO ad_spend
              (tenant_id, date, platform, campaign_id, campaign_name,
               sku, spend, impressions, clicks, conversions,
               attribution_method)
            VALUES ($1, $2, 'google', $3::text, $4, NULL, $5::numeric,
                    $6::bigint, $7::bigint, $8::int, 'proportional')
            ON CONFLICT DO NOTHING
            """,
            tenant_id,
            d,
            c["id"],
            c.get("name", ""),
            int(m.get("costMicros", 0)) / 1_000_000,
            int(m.get("impressions", 0)),
            int(m.get("clicks", 0)),
            int(m.get("conversions", 0)),
        )
        inserted += 1

    log.info(
        "google.sync_done",
        tenant_id=str(tenant_id),
        customer=customer_id,
        rows=inserted,
    )
    return inserted