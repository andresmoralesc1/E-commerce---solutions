"""Ecommerce Brain — FastAPI entry."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import close_db, init_db
from app.core.logging import log, setup_logging
from app.core.llm_providers import get_llm_client
from app.routers import (
    ads, agent, audit, auth, dashboard, oauth, products, reports,
    sync, tenants, webhooks,
)

setup_logging("DEBUG" if settings.debug else "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.starting", name=settings.app_name)
    await init_db()
    log.info("app.db_ready")
    yield
    log.info("app.stopping")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Brain de IA para ecommerces — margen neto real y decisiones automáticas",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(dashboard.router)
app.include_router(agent.router)
app.include_router(sync.router)
app.include_router(webhooks.router)
app.include_router(ads.router)
app.include_router(products.router)
app.include_router(reports.router)
app.include_router(oauth.router)
app.include_router(audit.router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "llm_provider": settings.llm_provider,
    }


@app.get("/api/health/llm")
async def llm_health() -> dict:
    try:
        client = get_llm_client()
        ok = await client.health()
        return {"ok": ok, "provider": settings.llm_provider}
    except Exception as e:
        return {"ok": False, "provider": settings.llm_provider, "error": str(e)}