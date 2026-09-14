"""Metrics endpoint — Prometheus-compatible.

Devuelve métricas en formato text/plain que Prometheus puede scrapear:
- braincountup_orders_total
- braincountup_pending_actions_total{status}
- braincountup_audit_events_total{action}
- braincountup_active_tenants
- brainhistogram_decide_latency_seconds

Para Prometheus real agregar scrape_config:
  - job_name: 'ecommerce-brain'
    static_configs: [{targets: ['localhost:5430']}]
"""
from __future__ import annotations

from prometheus_client import (
    CollectorRegistry, Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
)
from fastapi import APIRouter, Response

from app.core import db

router = APIRouter(tags=["metrics"])

# Registry propio (no el global, para evitar leakage entre tests)
registry = CollectorRegistry()

# ─── Metrics ─────────────────────────────────────────────────────────────

orders_total = Counter(
    "brain_orders_total",
    "Total orders synced",
    ["source", "tenant_id"],
    registry=registry,
)
pending_actions_gauge = Gauge(
    "brain_pending_actions",
    "Pending actions by status",
    ["status"],
    registry=registry,
)
audit_events_total = Counter(
    "brain_audit_events_total",
    "Audit events",
    ["action", "actor_kind"],
    registry=registry,
)
active_tenants_gauge = Gauge(
    "brain_active_tenants",
    "Number of active tenants",
    registry=registry,
)
decide_latency = Histogram(
    "brain_decide_latency_seconds",
    "Latency of /agent/decide",
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10],
    registry=registry,
)
llm_request_total = Counter(
    "brain_llm_requests_total",
    "LLM requests",
    ["provider", "status"],
    registry=registry,
)


async def update_dynamic_metrics() -> None:
    """Refresca métricas dinámicas desde DB. Llamar antes de cada scrape."""
    try:
        rows = await db.fetch(
            "SELECT status, COUNT(*) FROM pending_actions "
            "GROUP BY status"
        )
        for r in rows:
            pending_actions_gauge.labels(status=r["status"]).set(r["count"])

        n_tenants = await db.fetchval(
            "SELECT COUNT(*) FROM tenants WHERE active = TRUE"
        )
        active_tenants_gauge.set(n_tenants)
    except Exception:
        # Si DB no responde, devolver lo cacheado
        pass


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Endpoint Prometheus."""
    await update_dynamic_metrics()
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )