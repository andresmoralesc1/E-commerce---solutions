"use client";
import useSWR from "swr";
import {useRouter} from "next/navigation";
import {useEffect} from "react";
import {useParams} from "next/navigation";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {useTenant} from "@/lib/tenant";
import {KPICards} from "@/components/KPICards";
import {ProfitabilityTable} from "@/components/ProfitabilityTable";
import {
  StateDistributionChart,
  AdSpendVsRevenueChart,
  MarginPctChart,
} from "@/components/Charts";
import type {KPIs, ProfitabilityRow} from "@/lib/types";

export function DashboardClient() {
  const {token} = useAuth();
  const {activeTenantId} = useTenant();
  const router = useRouter();
  const {locale} = useParams<{locale: string}>();

  useEffect(() => {
    if (token === null) router.push(`/${locale}/login`);
  }, [token, locale, router]);

  const kpis = useSWR<KPIs>(
    token ? ["/api/dashboard/kpis", token, activeTenantId] : null,
    ([url, t]) => {
      const q = activeTenantId ? `${url}?tenant_id=${activeTenantId}` : url;
      return api<KPIs>(q, {token: t as string});
    },
    {refreshInterval: 30000},
  );
  const prof = useSWR<ProfitabilityRow[]>(
    token ? ["/api/dashboard/profitability?limit=200", token, activeTenantId] : null,
    ([url, t]) => {
      const sep = url.includes("?") ? "&" : "?";
      const q = activeTenantId ? `${url}${sep}tenant_id=${activeTenantId}` : url;
      return api<ProfitabilityRow[]>(q, {token: t as string});
    },
    {refreshInterval: 30000},
  );

  if (!token) return <p className="text-slate-400">Sin sesión</p>;
  if (kpis.isLoading || prof.isLoading)
    return <p className="text-slate-400">Cargando…</p>;
  if (kpis.error || prof.error)
    return (
      <p className="text-rose-400">
        Error: {String(kpis.error || prof.error)}
      </p>
    );

  const rows = prof.data ?? [];

  return (
    <>
      <KPICards data={kpis.data ?? emptyKPIs()} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <StateDistributionChart rows={rows} />
        <AdSpendVsRevenueChart rows={rows} />
      </div>
      <div className="mt-6">
        <MarginPctChart rows={rows} />
      </div>
      <section className="mt-6">
        <h2 className="text-lg font-semibold mb-3">
          🔥 Top 10 SKUs a pérdida / optimización
        </h2>
        <ProfitabilityTable rows={rows.slice(0, 10)} />
      </section>
    </>
  );
}

function emptyKPIs(): KPIs {
  return {
    revenue_total: 0,
    net_margin_total: 0,
    ad_spend_total: 0,
    cogs_total: 0,
    sku_total: 0,
    skus_burning: 0,
    money_burned_3d: 0,
  };
}