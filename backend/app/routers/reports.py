"""Reports router — daily morning report (placeholder Fase 4)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import TokenData, get_current_user
from app.services.agent_decision import decide_for_sku, queue_action
from app.services.profitability import kpis, list_profitability

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/morning")
async def morning_report(user: TokenData = Depends(get_current_user)) -> dict:
    """Genera reporte matutino: SKUs a pérdida + acciones recomendadas.

    Fase 2: retorna JSON con las decisiones.
    Fase 4: además las enqueue y las manda por WhatsApp vía Evolution.
    """
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")

    # Todos los tenants activos
    from app.core import db
    tenants = await db.fetch("SELECT id, name FROM tenants WHERE active=TRUE")
    actions_sent = 0
    errors = []
    for t in tenants:
        try:
            # SKUs a pérdida con ad spend reciente
            losing = await list_profitability(
                tenant_id=t["id"], state="A_PERDIDA", limit=50
            )
            for sk in losing:
                if float(sk["ad_spend_3d"]) <= 20:
                    continue
                decision = await decide_for_sku(t["id"], sk["sku"])
                queued = await queue_action(t["id"], sk["sku"], decision)
                if queued:
                    actions_sent += 1
        except Exception as e:
            errors.append({"tenant_id": str(t["id"]), "error": str(e)})

    summary = {
        "ok": True,
        "tenants_processed": len(tenants),
        "actions_sent": actions_sent,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return summary