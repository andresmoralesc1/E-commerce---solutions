export type SKUState = "GANADOR" | "A_OPTIMIZAR" | "EN_RIESGO" | "A_PERDIDA";

export interface KPIs {
  revenue_total: number;
  net_margin_total: number;
  ad_spend_total: number;
  cogs_total: number;
  sku_total: number;
  skus_burning: number;
  money_burned_3d: number;
}

export interface ProfitabilityRow {
  product_id: number;
  tenant_id: string;
  sku: string;
  title: string | null;
  stock: number;
  revenue_30d: number;
  cogs_total: number;
  shipping_total: number;
  gateway_fee_total: number;
  ad_spend_total: number;
  ad_spend_3d: number;
  net_margin_abs: number;
  net_margin_pct: number;
  roas_real: number | null;
  state: SKUState;
}

export interface PendingAction {
  id: string;
  tenant_id: string;
  sku: string | null;
  action_type: string;
  status: string;
  reasoning: string | null;
  whatsapp_message: string | null;
  confidence: number | null;
  created_at: string;
  expires_at: string;
}