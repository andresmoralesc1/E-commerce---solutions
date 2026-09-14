"""Reports router — daily morning report."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import TokenData, get_current_user
from app.services.agent_decision import decide_for_sku, queue_action
from app.services.profitability import kpis, list_profitability
from app.services.whatsapp import send_pending_action_message

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/morning")
async def morning_report(user: TokenData = Depends(get_current_user)) -> dict:
    """Morning report:
    1. Detecta SKUs A PERDIDA con ad_spend_3d > 20
    2. Genera pending_action por cada uno
    3. Envía WhatsApp al manager de cada tenant (vía Evolution API)

    Pensado para ejecutarse via n8n cron a las 8am, pero también
    funciona manualmente para pruebas.
    """
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers / cron jobs")

    from app.core import db
    tenants = await db.fetch("SELECT id, name FROM tenants WHERE active=TRUE")
    actions_queued = 0
    whatsapp_sent = 0
    whatsapp_errors = []
    errors = []

    for t in tenants:
        try:
            losing = await list_profitability(
                tenant_id=t["id"], state="A_PERDIDA", limit=50
            )
            for sk in losing:
                if float(sk["ad_spend_3d"]) <= 20:
                    continue
                decision = await decide_for_sku(t["id"], sk["sku"])
                queued = await queue_action(t["id"], sk["sku"], decision)
                if queued:
                    actions_queued += 1
                    # Enviar WhatsApp inmediatamente
                    send_result = await send_pending_action_message(queued["id"])
                    if send_result.ok:
                        whatsapp_sent += 1
                    else:
                        whatsapp_errors.append({
                            "tenant_id": str(t["id"]),
                            "sku": sk["sku"],
                            "mode": send_result.mode,
                            "error": send_result.error,
                        })
        except Exception as e:
            errors.append({"tenant_id": str(t["id"]), "error": str(e)})

    summary = {
        "ok": True,
        "tenants_processed": len(tenants),
        "actions_queued": actions_queued,
        "whatsapp_sent": whatsapp_sent,
        "whatsapp_errors": whatsapp_errors,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return summary


@router.post("/morning/dry-run")
async def morning_report_dry_run(user: TokenData = Depends(get_current_user)) -> dict:
    """Versión que solo muestra qué haría, sin enviar."""
    if not user.superuser:
        raise HTTPException(status_code=403, detail="Solo superusers")

    from app.core import db
    tenants = await db.fetch("SELECT id, name FROM tenants WHERE active=TRUE")
    would_act = []
    for t in tenants:
        losing = await list_profitability(
            tenant_id=t["id"], state="A_PERDIDA", limit=50
        )
        for sk in losing:
            if float(sk["ad_spend_3d"]) <= 20:
                continue
            would_act.append({
                "tenant_id": str(t["id"]),
                "sku": sk["sku"],
                "margin_pct": sk["net_margin_pct"],
                "ad_spend_3d": sk["ad_spend_3d"],
                "message_preview": (
                    f"🚨 {sk['sku']} a pérdida ({sk['net_margin_pct']:.1f}%) "
                    f"con ${sk['ad_spend_3d']:.0f} en ads"
                ),
            })

    return {"ok": True, "would_act_count": len(would_act), "items": would_act}