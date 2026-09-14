"""
Genera datos sintéticos realistas para demos del sistema.

Crea (si no existe):
- 1 tenant demo "Tienda Demo"
- 25 SKUs en categorías variadas con COGS
- ~300 órdenes distribuidas en últimos 30 días
- ad_spend por SKU últimos 90 días

El sistema detecta los 4 estados: GANADOR, A_OPTIMIZAR, EN_RIESGO, A_PERDIDA.

Uso:
    docker compose exec backend python scripts/seed_demo.py
    docker compose exec backend python scripts/seed_demo.py --tenant-name "Mi Tienda"
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import asyncpg
import os

DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://brain:brain_change_me_strong_password"
    "@postgres:5432/brain",
)
# asyncpg usa postgresql:// pero acepta también postgres://
if DSN.startswith("postgres://"):
    DSN = DSN.replace("postgres://", "postgresql://", 1)

# ─── Catálogo demo ────────────────────────────────────────────────────────
PRODUCTS = [
    # sku, title, cost (COGS), price, stock, category
    ("CAM-BLK-001", "Camiseta Básica Negra",     12000, 35000, 80,  "apparel"),
    ("CAM-WHT-002", "Camiseta Básica Blanca",     12000, 35000, 65,  "apparel"),
    ("CAM-AZU-003", "Camiseta Polo Azul",         18500, 48000, 40,  "apparel"),
    ("PAN-CLASS-01","Pantalón Clásico Slim",      28000, 75000, 30,  "apparel"),
    ("PAN-JEAN-02", "Jeans Premium Dark Wash",    35000, 95000, 22,  "apparel"),
    ("ZAP-RUN-001", "Zapatillas Running Pro",     65000, 159000, 18, "footwear"),
    ("ZAP-CAS-002", "Zapatillas Casual Urban",    45000, 119000, 35, "footwear"),
    ("BOL-LTH-01", "Bolso Cuero Premium",         85000, 219000, 12, "accessories"),
    ("GAF-RET-01", "Gafas de Sol Retro",         18000, 59000,  45, "accessories"),
    ("REL-AVI-01", "Reloj Aviador Dorado",        95000, 245000, 10, "accessories"),
    # Productos con márgenes ajustados (EN_RIESGO)
    ("CAR-COT-01", "Cartera de Tela",             28000, 49000,  28, "accessories"),
    ("BUF-WOOL-01","Bufanda Lana Merino",         32000, 55000,  20, "apparel"),
    # Productos a pérdida (COGS alto vs precio)
    ("PRO-IMP-01", "Producto Importado Test",     88000, 95000,   8, "imported"),  # margen muy bajo
    ("PRO-IMP-02", "Producto Importado Test 2",   92000, 98000,   5, "imported"),  # margen mínimo
    # Productos baratos y rentables
    ("CAL-COT-01", "Calcetines Algodón Pack x3",   8500, 29000, 120, "apparel"),
    ("GUA-CUO-01", "Guantes Cuero Invierno",      22000, 59000,  40, "accessories"),
    ("GOR-BAS-01", "Gorra Básica Logo",            9500, 32000,  90, "accessories"),
    # Más productos mixtos
    ("CHA-VES-01", "Chaleco Vestir Slim",         45000, 109000, 22, "apparel"),
    ("FAL-MOM-01", "Falda Mom Fit",                28000, 72000,  35, "apparel"),
    ("VES-CAS-01", "Vestido Casual Verano",       38000, 89000,  28, "apparel"),
    ("BLU-DEN-01", "Blusa Denim Vintage",         35000, 85000,  18, "apparel"),
    ("CHA-CUI-01", "Chaqueta Cuero Biker",       145000, 329000,  8, "apparel"),
    ("BOT-TIM-01", "Botines Timber-style",        78000, 189000, 15, "footwear"),
    ("MOC-CAS-01", "Mocasines Casual",             55000, 129000, 25, "footwear"),
    ("PAN-CAR-01", "Pantalón Cargo",               42000, 99000,  30, "apparel"),
]


async def seed(tenant_name: str = "Tienda Demo", force: bool = False) -> None:
    conn = await asyncpg.connect(DSN)

    try:
        # 1) Tenant
        existing = await conn.fetchval(
            "SELECT id FROM tenants WHERE name = $1 LIMIT 1",
            tenant_name,
        )
        if existing and not force:
            print(f"✓ Tenant '{tenant_name}' ya existe ({existing})")
            tenant_id = existing
        else:
            tenant_id = await conn.fetchval(
                """
                INSERT INTO tenants (name, source, locale, settings)
                VALUES ($1, 'shopify', 'es',
                        '{"currency":"COP","timezone":"America/Bogota"}'::jsonb)
                RETURNING id
                """,
                tenant_name,
            )
            print(f"✓ Tenant '{tenant_name}' creado: {tenant_id}")

        # 2) Products
        n_products = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE tenant_id = $1", tenant_id
        )
        if n_products > 0 and not force:
            print(f"✓ {n_products} productos ya existen")
        else:
            await conn.executemany(
                """
                INSERT INTO products
                  (tenant_id, sku, title, cost, weight_kg, stock, metadata)
                VALUES ($1, $2, $3, $4, $5, $6,
                        jsonb_build_object('category', $7::text))
                ON CONFLICT (tenant_id, sku) DO NOTHING
                """,
                [
                    (tenant_id, sku, title, cost,
                     Decimal(random.uniform(0.1, 1.5)).quantize(Decimal("0.001")),
                     stock, cat)
                    for sku, title, cost, price, stock, cat in PRODUCTS
                ],
            )
            print(f"✓ {len(PRODUCTS)} productos insertados")

        # 3) Orders últimos 30 días — volumen variable por SKU
        n_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE tenant_id = $1", tenant_id
        )
        if n_orders > 0 and not force:
            print(f"✓ {n_orders} órdenes ya existen")
        else:
            today = datetime.now(timezone.utc)
            n_inserted = 0
            for day_offset in range(30):
                day = today - timedelta(days=day_offset)
                # volumen diario entre 6 y 14 órdenes
                daily_count = random.randint(6, 14)
                for _ in range(daily_count):
                    sku, title, cogs, price, stock, cat = random.choice(PRODUCTS)
                    # 1-3 unidades por pedido
                    qty = random.randint(1, 3)
                    discount = random.choice([0, 0, 0, 5000, 10000])
                    shipping = random.choice([8000, 10000, 12000, 15000])
                    gateway_pct = 0.035
                    subtotal = price * qty
                    total = subtotal - discount + shipping
                    gateway_fee = float(total) * gateway_pct
                    placed = day.replace(
                        hour=random.randint(8, 22),
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59),
                    )
                    external_id = f"SEED-{day.strftime('%Y%m%d')}-{n_inserted:05d}"

                    order_id = await conn.fetchval(
                        """
                        INSERT INTO orders
                          (tenant_id, external_id, customer_email, status, currency,
                            subtotal, discount_total, shipping_cost, tax_total, total,
                            gateway_fee_estimated, placed_at)
                        VALUES ($1,$2,$3,'paid','COP',$4,$5,$6,0,$7,$8,$9)
                        RETURNING id
                        """,
                        tenant_id, external_id,
                        f"customer{random.randint(1, 9999)}@demo.co",
                        float(subtotal), float(discount), float(shipping),
                        float(total), gateway_fee, placed,
                    )
                    await conn.execute(
                        """
                        INSERT INTO order_items
                          (order_id, sku, quantity, unit_price, total_price, discount)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        """,
                        order_id, sku, qty, float(price),
                        float(price * qty), float(discount),
                    )
                    n_inserted += 1
            print(f"✓ {n_inserted} órdenes insertadas (30 días)")

        # 4) ad_spend últimos 90 días — atribución mixta
        n_ads = await conn.fetchval(
            "SELECT COUNT(*) FROM ad_spend WHERE tenant_id = $1", tenant_id
        )
        if n_ads > 0 and not force:
            print(f"✓ {n_ads} filas ad_spend ya existen")
        else:
            today = datetime.now(timezone.utc).date()
            n_inserted = 0
            for day_offset in range(90):
                date = today - timedelta(days=day_offset)
                for sku, title, cogs, price, stock, cat in PRODUCTS:
                    # 70% de SKUs reciben ads en un día cualquiera
                    if random.random() > 0.7:
                        continue
                    # Spend diario entre 5k y 80k COP
                    spend = random.randint(5000, 80000)
                    # 80% atribuido a SKU (UTM), 20% a la campaña (sin SKU)
                    has_utm = random.random() < 0.8
                    campaign_id = f"camp_{random.randint(1, 8)}"
                    platform = random.choice(["meta", "google"])
                    impressions = random.randint(1000, 50000)
                    clicks = int(impressions * random.uniform(0.01, 0.05))
                    conversions = random.randint(0, max(1, clicks // 50))

                    await conn.execute(
                        """
                        INSERT INTO ad_spend
                          (tenant_id, date, platform, campaign_id, campaign_name,
                            sku, spend, impressions, clicks, conversions,
                            attribution_method)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        tenant_id, date, platform, campaign_id,
                        f"Camp {campaign_id}",
                        sku if has_utm else None,
                        spend, impressions, clicks, conversions,
                        "utm" if has_utm else "proportional",
                    )
                    n_inserted += 1
            print(f"✓ {n_inserted} filas ad_spend insertadas (90 días)")

        # 5) Refresh vista materializada
        await conn.execute("REFRESH MATERIALIZED VIEW profitability_mv")
        print("✓ profitability_mv refrescada")

        # 6) Resumen
        summary = await conn.fetchrow(
            """
            SELECT
              COUNT(*)                                                  AS total,
              COUNT(*) FILTER (WHERE classify_sku(net_margin_pct)='GANADOR')     AS ganador,
              COUNT(*) FILTER (WHERE classify_sku(net_margin_pct)='A_OPTIMIZAR') AS optimizar,
              COUNT(*) FILTER (WHERE classify_sku(net_margin_pct)='EN_RIESGO')   AS riesgo,
              COUNT(*) FILTER (WHERE classify_sku(net_margin_pct)='A_PERDIDA')   AS perdida
            FROM profitability_mv
            WHERE tenant_id = $1
              AND revenue_30d > 0
            """,
            tenant_id,
        )
        print()
        print(f"📊 Resumen del tenant {tenant_id}:")
        print(f"   SKUs con ventas en 30d: {summary['total']}")
        print(f"   🟢 GANADOR      : {summary['ganador']}")
        print(f"   🟡 A_OPTIMIZAR  : {summary['optimizar']}")
        print(f"   🟠 EN_RIESGO    : {summary['riesgo']}")
        print(f"   🔴 A_PERDIDA    : {summary['perdida']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-name", default="Tienda Demo")
    parser.add_argument("--force", action="store_true",
                        help="Borra y recrea datos del tenant")
    args = parser.parse_args()

    asyncio.run(seed(args.tenant_name, args.force))