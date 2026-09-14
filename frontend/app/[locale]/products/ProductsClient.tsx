"use client";
import {useState} from "react";
import useSWR from "swr";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {useTenant} from "@/lib/tenant";
import {ProfitabilityTable} from "@/components/ProfitabilityTable";
import type {SKUState, ProfitabilityRow} from "@/lib/types";

const FILTERS: (SKUState | "ALL")[] = [
  "ALL", "GANADOR", "A_OPTIMIZAR", "EN_RIESGO", "A_PERDIDA",
];

export function ProductsClient() {
  const {token} = useAuth();
  const {activeTenantId} = useTenant();
  const [filter, setFilter] = useState<SKUState | "ALL">("ALL");

  const base =
    filter === "ALL"
      ? "/api/dashboard/profitability?limit=200"
      : `/api/dashboard/profitability?state=${filter}&limit=200`;

  const url = activeTenantId ? `${base}&tenant_id=${activeTenantId}` : base;

  const {data, error, isLoading} = useSWR<ProfitabilityRow[]>(
    token ? [url, token] : null,
    ([u, t]) => api<ProfitabilityRow[]>(u, {token: t as string}),
    {refreshInterval: 30000},
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 text-sm rounded border ${
              filter === f
                ? "bg-emerald-500 border-emerald-400 text-white"
                : "bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      {isLoading && <p>Cargando…</p>}
      {error && <p className="text-rose-400">{String(error)}</p>}
      {data && (
          <>
            <p className="text-xs text-slate-400">
              {data.length} resultados
            </p>
            <ProfitabilityTable rows={data} />
          </>
        )}
    </div>
  );
}