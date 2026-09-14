"""Products router — listar + asignar COGS manualmente."""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core import db
from app.core.security import TokenData, get_current_user, get_tenant_ids
from app.services.profitability import refresh_view

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductOut(BaseModel):
    id: int
    tenant_id: UUID
    sku: str
    title: str | None
    cost: float | None
    weight_kg: float | None
    stock: int


class CostUpdate(BaseModel):
    cost: Decimal = Field(ge=0)


@router.get("", response_model=list[ProductOut])
async def list_products(
    tenant_id: UUID = Query(...),
    search: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    user: TokenData = Depends(get_current_user),
) -> list[ProductOut]:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")

    where = ["tenant_id = $1"]
    args: list = [tenant_id]
    if search:
        args.append(f"%{search}%")
        where.append(f"(sku ILIKE ${len(args)} OR title ILIKE ${len(args)})")
    args.append(limit)

    rows = await db.fetch(
        f"""
        SELECT id, tenant_id, sku, title, cost, weight_kg, stock
        FROM products
        WHERE {' AND '.join(where)}
        ORDER BY sku
        LIMIT ${len(args)}
        """,
        *args,
    )
    return [ProductOut(**dict(r)) for r in rows]


@router.put("/{sku}/cost", response_model=ProductOut)
async def update_cost(
    sku: str,
    body: CostUpdate,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> ProductOut:
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")

    row = await db.fetchrow(
        """
        UPDATE products
        SET cost = $1, updated_at = NOW()
        WHERE tenant_id = $2 AND sku = $3
        RETURNING id, tenant_id, sku, title, cost, weight_kg, stock
        """,
        float(body.cost),
        tenant_id,
        sku,
    )
    if not row:
        raise HTTPException(status_code=404, detail="product_not_found")

    # Refrescar vista materializada para reflejar nuevo COGS
    await refresh_view()
    return ProductOut(**dict(row))


class BulkCostUpdate(BaseModel):
    items: list[dict]


@router.post("/bulk-cost")
async def bulk_update_cost(
    body: BulkCostUpdate,
    tenant_id: UUID = Query(...),
    user: TokenData = Depends(get_current_user),
) -> dict:
    """Actualiza COGS de múltiples SKUs de una vez (vía CSV/import)."""
    allowed = await get_tenant_ids(user)
    if not user.superuser and tenant_id not in allowed:
        raise HTTPException(status_code=403, detail="Sin acceso")

    n = 0
    for item in body.items:
        sku = item.get("sku")
        cost = item.get("cost")
        if not sku or cost is None:
            continue
        await db.execute(
            """
            UPDATE products SET cost = $1, updated_at = NOW()
            WHERE tenant_id = $2 AND sku = $3
            """,
            float(cost), tenant_id, sku,
        )
        n += 1
    await refresh_view()
    return {"ok": True, "updated": n}