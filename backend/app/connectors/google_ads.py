"""Google Ads connector.

Fase 1: scaffold.
Fase 3: OAuth + Google Ads API con segments = utm_content (custom).
"""
from datetime import date
from uuid import UUID

from app.core.logging import log


async def fetch_ad_spend(
    tenant_id: UUID,
    refresh_token: str,
    customer_id: str,
    since: date,
    until: date,
) -> int:
    log.info("google_ads.sync_stub", tenant_id=str(tenant_id))
    return 0