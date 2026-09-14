"""Agent router — decide, confirm, list pending."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import db
from app.core.security import TokenData, get_current_user, get_tenant_ids
from app.schemas.agent import (
    ConfirmIn,
    DecideIn,
    DecideOut,
    PendingActionOut,
)
from app.services.agent_decision import (
    confirm_and_execute,
    decide_for_sku,
    queue_action,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _parse_pending(row: dict) -> dict:
    """Deserializa campos jsonb que asyncpg devuelve como str."""
    import json as _json
    for field in ("execution_result",):
        v = row.get(field)
        if isinstance(v, str) and v:
            try:
                row[field] = _json.loads(v)
            except Exception:
                row[field] = None
    return row


@router.post("/decide", response_model=DecideOut)
async def decide(
    body: DecideIn,
    user: TokenData = Depends(get_current_user),
) -> DecideOut:
    allowed = await get_tenant_ids(user)
    if not user.superuser and body.tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso al tenant")

    decision = await decide_for_sku(body.tenant_id, body.sku)
    queued = await queue_action(body.tenant_id, body.sku, decision)
    if queued is None:
        raise HTTPException(status_code=400, detail="No action required")
    return DecideOut(
        action_id=queued["id"],
        sku=body.sku,
        action=decision.action,
        confidence=decision.confidence,
        reasoning=decision.reasoning,
        whatsapp_message=decision.whatsapp_message,
        payload=decision.payload,
    )


@router.post("/confirm/{action_id}")
async def confirm(
    action_id: str,
    body: ConfirmIn,
    user: TokenData = Depends(get_current_user),
) -> dict:
    pa = await db.fetchrow(
        "SELECT tenant_id FROM pending_actions WHERE id = $1", action_id
    )
    if not pa:
        raise HTTPException(status_code=404, detail="action_not_found")
    allowed = await get_tenant_ids(user)
    if not user.superuser and pa["tenant_id"] not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")
    return await confirm_and_execute(action_id, body.approved)


@router.get("/pending", response_model=list[PendingActionOut])
async def list_pending(
    tenant_id: UUID | None = Query(None),
    status_filter: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    user: TokenData = Depends(get_current_user),
) -> list[PendingActionOut]:
    allowed = await get_tenant_ids(user)
    if user.superuser:
        if tenant_id is not None:
            rows = await db.fetch(
                """
                SELECT * FROM pending_actions
                WHERE tenant_id = $1 AND status = $2
                ORDER BY created_at DESC LIMIT $3
                """,
                tenant_id, status_filter, limit,
            )
        else:
            rows = await db.fetch(
                """
                SELECT * FROM pending_actions
                WHERE status = $1
                ORDER BY created_at DESC LIMIT $2
                """,
                status_filter, limit,
            )
    else:
        if not allowed:
            return []
        rows = await db.fetch(
            """
            SELECT * FROM pending_actions
            WHERE tenant_id = ANY($1::uuid[]) AND status = $2
            ORDER BY created_at DESC LIMIT $3
            """,
            allowed, status_filter, limit,
        )
    return [PendingActionOut(**_parse_pending(dict(r))) for r in rows]