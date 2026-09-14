-- ============================================================================
-- Ecommerce Brain — Schema inicial multi-tenant
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Tenants ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  source VARCHAR(20) NOT NULL CHECK (source IN ('shopify','woocommerce')),
  credentials JSONB NOT NULL DEFAULT '{}'::jsonb,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  locale VARCHAR(5) NOT NULL DEFAULT 'es',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_active ON tenants(active);

-- ─── Users (auth JWT) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  superuser BOOLEAN NOT NULL DEFAULT FALSE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pivot: user <-> tenants (multi-tenant desde día 1)
CREATE TABLE IF NOT EXISTS user_tenants (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL DEFAULT 'owner', -- owner | admin | viewer
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, tenant_id)
);

-- ─── Products ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sku VARCHAR(100) NOT NULL,
  title TEXT,
  cost NUMERIC(12,2),                       -- COGS manual o importado
  weight_kg NUMERIC(8,3),
  stock INTEGER NOT NULL DEFAULT 0,
  external_id VARCHAR(100),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(tenant_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_products_tenant ON products(tenant_id);

-- ─── Orders ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  external_id VARCHAR(100) NOT NULL,
  customer_email VARCHAR(255),
  status VARCHAR(50),
  currency VARCHAR(10) NOT NULL DEFAULT 'COP',
  subtotal NUMERIC(14,2) NOT NULL DEFAULT 0,
  discount_total NUMERIC(14,2) NOT NULL DEFAULT 0,
  shipping_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  tax_total NUMERIC(14,2) NOT NULL DEFAULT 0,
  total NUMERIC(14,2) NOT NULL DEFAULT 0,
  gateway_fee_estimated NUMERIC(14,2) NOT NULL DEFAULT 0,
  placed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(tenant_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_placed ON orders(tenant_id, placed_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(tenant_id, status);

-- ─── Order Items ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
  sku VARCHAR(100) NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
  total_price NUMERIC(12,2) NOT NULL DEFAULT 0,
  discount NUMERIC(12,2) NOT NULL DEFAULT 0,
  refunded BOOLEAN NOT NULL DEFAULT FALSE,
  refund_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_items_sku ON order_items(sku);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

-- ─── Ad Spend ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ad_spend (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  platform VARCHAR(20) NOT NULL CHECK (platform IN ('meta','google')),
  campaign_id VARCHAR(100),
  campaign_name TEXT,
  adset_id VARCHAR(100),
  ad_id VARCHAR(100),
  sku VARCHAR(100),                        -- atribuido por utm_content
  spend NUMERIC(12,2) NOT NULL DEFAULT 0,
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  conversions INTEGER NOT NULL DEFAULT 0,
  attribution_method VARCHAR(20) NOT NULL DEFAULT 'utm',  -- utm | proportional
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ad_spend_tenant_date ON ad_spend(tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_ad_spend_sku ON ad_spend(tenant_id, sku, date DESC);
CREATE INDEX IF NOT EXISTS idx_ad_spend_campaign ON ad_spend(tenant_id, campaign_id, date DESC);

-- ─── Pending Actions (cola de decisiones esperando aprobación) ────────
CREATE TABLE IF NOT EXISTS pending_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sku VARCHAR(100),
  action_type VARCHAR(50) NOT NULL,        -- pause_ads | scale_budget | increase_price | renegotiate_cogs
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  whatsapp_message TEXT,
  reasoning TEXT,
  confidence NUMERIC(4,3),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  -- pending | approved | rejected | executed | failed | expired
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days',
  approved_at TIMESTAMPTZ,
  executed_at TIMESTAMPTZ,
  response_text TEXT,
  execution_result JSONB
);

CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_actions_tenant ON pending_actions(tenant_id, status);

-- ─── Audit log (todas las decisiones ejecutadas) ──────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
  actor VARCHAR(50) NOT NULL,              -- system | user:<id> | whatsapp:<phone>
  action VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id, created_at DESC);

-- ─── Vista materializada: rentabilidad por SKU (últimos 30 días) ──────
DROP MATERIALIZED VIEW IF EXISTS profitability_mv;
CREATE MATERIALIZED VIEW profitability_mv AS
WITH
  -- ventas (revenue) por SKU en ventana 30d
  sales AS (
    SELECT
      o.tenant_id,
      oi.sku,
      SUM(oi.total_price - oi.discount)         AS revenue,
      SUM(oi.quantity * COALESCE(p.cost, 0))    AS cogs,
      SUM(oi.quantity)                          AS units_sold,
      SUM(oi.total_price) * 0.035               AS gateway_fee_est,
      SUM(CASE WHEN oi.refunded THEN oi.refund_amount ELSE 0 END) AS refunds,
      COUNT(*)                                  AS orders_count
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    LEFT JOIN products p ON p.tenant_id = o.tenant_id AND p.sku = oi.sku
    WHERE o.placed_at >= CURRENT_DATE - INTERVAL '30 days'
      AND o.status NOT IN ('cancelled','refunded')
    GROUP BY o.tenant_id, oi.sku
  ),
  -- shipping asignado a cada SKU (prorrateo por revenue dentro del pedido)
  shipping_alloc AS (
    SELECT
      o.tenant_id,
      oi.sku,
      SUM(
        o.shipping_cost * (oi.total_price / NULLIF(o.subtotal, 0))
      ) AS shipping_total
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.placed_at >= CURRENT_DATE - INTERVAL '30 days'
      AND o.status NOT IN ('cancelled','refunded')
    GROUP BY o.tenant_id, oi.sku
  ),
  -- ad spend por SKU (ventana 30d)
  ads AS (
    SELECT tenant_id, sku, SUM(spend) AS ad_spend
    FROM ad_spend
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY tenant_id, sku
  ),
  -- ad spend últimos 3 días (para regla de pause del agente)
  ads_3d AS (
    SELECT tenant_id, sku, SUM(spend) AS ad_spend_3d
    FROM ad_spend
    WHERE date >= CURRENT_DATE - INTERVAL '3 days'
    GROUP BY tenant_id, sku
  )
SELECT
  p.id                                              AS product_id,
  p.tenant_id,
  p.sku,
  p.title,
  p.stock,
  COALESCE(s.revenue, 0)                            AS revenue_30d,
  COALESCE(s.cogs, 0)                               AS cogs_total,
  COALESCE(sa.shipping_total, 0)                    AS shipping_total,
  COALESCE(s.gateway_fee_est, 0)                    AS gateway_fee_total,
  COALESCE(ad.ad_spend, 0)                          AS ad_spend_total,
  COALESCE(ad3.ad_spend_3d, 0)                      AS ad_spend_3d,
  COALESCE(s.refunds, 0)                            AS refunds_total,
  COALESCE(s.units_sold, 0)                         AS units_sold,
  COALESCE(s.orders_count, 0)                       AS orders_count,
  -- margen neto
  (COALESCE(s.revenue, 0)
    - COALESCE(s.cogs, 0)
    - COALESCE(sa.shipping_total, 0)
    - COALESCE(s.gateway_fee_est, 0)
    - COALESCE(ad.ad_spend, 0)
    - COALESCE(s.refunds, 0) * 1.5                  -- refund sale + handling
  )                                                 AS net_margin_abs,
  CASE WHEN COALESCE(s.revenue, 0) > 0 THEN
    ((COALESCE(s.revenue, 0)
      - COALESCE(s.cogs, 0)
      - COALESCE(sa.shipping_total, 0)
      - COALESCE(s.gateway_fee_est, 0)
      - COALESCE(ad.ad_spend, 0)
      - COALESCE(s.refunds, 0) * 1.5
    ) / s.revenue) * 100
  ELSE 0 END                                        AS net_margin_pct,
  -- ROAS real: revenue / (ad_spend + cogs)
  CASE WHEN (COALESCE(ad.ad_spend, 0) + COALESCE(s.cogs, 0)) > 0 THEN
    COALESCE(s.revenue, 0) / (COALESCE(ad.ad_spend, 0) + COALESCE(s.cogs, 0))
  ELSE NULL END                                     AS roas_real
FROM products p
LEFT JOIN sales       s   ON s.tenant_id  = p.tenant_id AND s.sku  = p.sku
LEFT JOIN shipping_alloc sa ON sa.tenant_id = p.tenant_id AND sa.sku = p.sku
LEFT JOIN ads         ad  ON ad.tenant_id = p.tenant_id AND ad.sku = p.sku
LEFT JOIN ads_3d      ad3 ON ad3.tenant_id= p.tenant_id AND ad3.sku= p.sku
WHERE p.sku IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_profitability_mv
  ON profitability_mv(tenant_id, sku);

CREATE INDEX IF NOT EXISTS idx_profitability_margin
  ON profitability_mv(net_margin_pct);

-- ─── Trigger updated_at genérico ───────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY['tenants','users','products','orders']) LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s; CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION set_updated_at();',
      t, t, t, t
    );
  END LOOP;
END$$;

-- ─── Función: clasificar SKU según % margen ───────────────────────────
CREATE OR REPLACE FUNCTION classify_sku(pct NUMERIC)
RETURNS VARCHAR(20) AS $$
BEGIN
  IF pct IS NULL THEN RETURN 'A_OPTIMIZAR'; END IF;
  IF pct > 30 THEN RETURN 'GANADOR'; END IF;
  IF pct > 15 THEN RETURN 'A_OPTIMIZAR'; END IF;
  IF pct > 0  THEN RETURN 'EN_RIESGO'; END IF;
  RETURN 'A_PERDIDA';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ─── Seed usuario superuser (cambiar password en producción) ──────────
-- password: brain123 (bcrypt generado con cost 12, ESTO ES UN PLACEHOLDER)
-- El backend genera el password del primer superuser via /auth/bootstrap
-- si users está vacío. No se crean credenciales por defecto aquí.