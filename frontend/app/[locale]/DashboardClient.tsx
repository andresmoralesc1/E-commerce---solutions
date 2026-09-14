"use client";
import useSWR from "swr";
import {useRouter} from "next/navigation";
import {useEffect} from "react";
import {useParams} from "next/navigation";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {KPICards} from "@/components/KPICards";
import {ProfitabilityTable} from "@/components/ProfitabilityTable";
import type {KPIs, ProfitabilityRow} from "@/lib/types";

export function DashboardClient() {
  const {token} = useAuth();
  const router = useRouter();
  const {locale} = useParams<{locale: string}>();

  useEffect(() => {
    if (token === null) router.push(`/${locale}/login`);
  }, [token, locale, router]);

  const kpis = useSWR<KPIs>(
    token ? ["/api/dashboard/kpis", token] : null,
    ([url, t]) => api<KPIs>(url, {token: t as string}),
  );
  const prof = useSWR<ProfitabilityRow[]>(
    token ? ["/api/dashboard/profitability?limit=10", token] : null,
    ([url, t]) => api<ProfitabilityRow[]>(url, {token: t as string}),
  );

  if (!token) return <p className="text-slate-400">Sin sesión</p>;
  if (kpis.isLoading || prof.isLoading)
    return <p className="text-slate-400">Cargando…</p>;
  if (kpis.error || prof.error)
    return <p className="text-rose-400">Error: {String(kpis.error || prof.error)}</p>;

  return (
    <>
      <KPICards data={kpis.data ?? emptyKPIs()} />
      <section>
        <h2 className="text-lg font-semibold mb-3">Top 10 SKUs por urgencia</h2>
        <ProfitabilityTable rows={prof.data ?? []} />
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