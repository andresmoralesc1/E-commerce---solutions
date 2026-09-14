"""WhatsApp router — envío manual + estado Evolution + bulk send."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import TokenData, get_current_user
from app.services.whatsapp import send_pending_action_message, send_text

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


class SendIn(BaseModel):
    text: str
    phone: str | None = None


class BulkSendIn(BaseModel):
    tenant_ids: list[UUID]


@router.post("/send")
async def send_message(
    body: SendIn,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")
    result = await send_text(tenant_id, body.text, phone=body.phone)
    return {
        "ok": result.ok,
        "mode": result.mode,
        "error": result.error,
        "provider_response": result.provider_response,
    }


@router.post("/send-pending/{action_id}")
async def send_pending(
    action_id: UUID,
    user: TokenData = Depends(get_current_user),
) -> dict:
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")
    result = await send_pending_action_message(action_id)
    return {
        "ok": result.ok,
        "mode": result.mode,
        "error": result.error,
        "provider_response": result.provider_response,
    }


@router.get("/evolution/status")
async def evolution_status() -> dict:
    """Comprueba el estado de Evolution API."""
    import httpx
    from app.core.config import settings
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{settings.evolution_api_url}/",
                headers={"apikey": settings.evolution_api_key},
            )
            if r.status_code == 200:
                return {"ok": True, "evolution": "up", "data": r.json()}
            return {"ok": False, "evolution": "error", "status": r.status_code}
    except Exception as e:
        return {"ok": False, "evolution": "down", "error": str(e)}