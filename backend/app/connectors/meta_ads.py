"""Meta Marketing API connector.

Fase 1: scaffold.
Fase 3: completar OAuth flow + pull insights con breakdown por UTM content.
"""
from datetime import date
from typing import Any
from uuid import UUID

import httpx

from app.core import db
from app.core.logging import log

GRAPH_API = "https://graph.facebook.com/v21.0"


async def fetch_ad_spend(
    tenant_id: UUID,
    access_token: str,
    ad_account_id: str,
    since: date,
    until: date,
) -> int:
    """Pull ad spend con breakdown por UTM content (= SKU)."""
    params: dict[str, Any] = {
        "level": "ad",
        "fields": "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
                  "spend,impressions,clicks,actions",
        "time_range": json_dumps_range(since, until),
        "time_increment": 1,
        "breakdowns": "none",
        "access_token": access_token,
    }
    # TODO Fase 3: pagination + breakdown con action_breakdowns=['action_type']
    log.info("meta.sync_stub", tenant_id=str(tenant_id))
    return 0


def json_dumps_range(since: date, until: date) -> str:
    import json
    return json.dumps({
        "since": since.isoformat(),
        "until": until.isoformat(),
    })