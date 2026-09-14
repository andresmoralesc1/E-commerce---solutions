"""Tests de integración — endpoints del backend.

Requiere DB corriendo. Usa la DB de docker-compose si está disponible.
"""
import asyncio
import os
from uuid import uuid4

import pytest
import asyncpg

DSN = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql://brain:braindemo123@localhost:5432/brain"),
)


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DSN)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_classify_sku_sql_function(db):
    """La función SQL classify_sku debe estar registrada y funcionar."""
    rows = await db.fetch(
        "SELECT classify_sku(50.0) AS a, classify_sku(20.0) AS b, "
        "classify_sku(8.0) AS c, classify_sku(-5.0) AS d, classify_sku(NULL) AS e"
    )
    r = dict(rows[0])
    assert r["a"] == "GANADOR"
    assert r["b"] == "A_OPTIMIZAR"
    assert r["c"] == "EN_RIESGO"
    assert r["d"] == "A_PERDIDA"
    # NULL → default A_OPTIMIZAR
    assert r["e"] == "A_OPTIMIZAR"


@pytest.mark.asyncio
async def test_tenants_table_exists(db):
    rows = await db.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    tables = [r["table_name"] for r in rows]
    expected = ["tenants", "users", "products", "orders", "order_items",
                "ad_spend", "pending_actions", "audit_log"]
    for t in expected:
        assert t in tables, f"missing table: {t}"


@pytest.mark.asyncio
async def test_profitability_mv_exists(db):
    rows = await db.fetch(
        "SELECT matviewname FROM pg_matviews WHERE matviewname='profitability_mv'"
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_user_tenants_pivot(db):
    """La tabla pivot user_tenants debe existir y tener columnas correctas."""
    rows = await db.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='user_tenants'"
    )
    cols = [r["column_name"] for r in rows]
    assert "user_id" in cols
    assert "tenant_id" in cols
    assert "role" in cols