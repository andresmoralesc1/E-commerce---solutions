"use client";
import {useState} from "react";
import useSWR from "swr";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {useTenant} from "@/lib/tenant";
import {ApproveButton} from "@/components/ApproveButton";
import type {PendingAction} from "@/lib/types";

export function PendingClient() {
  const {token} = useAuth();
  const {activeTenantId} = useTenant();
  const [statusFilter, setStatusFilter] = useState("pending");

  const base = `/api/agent/pending?status_filter=${statusFilter}&limit=50`;
  const url = activeTenantId ? `${base}&tenant_id=${activeTenantId}` : base;

  const {data, error, isLoading, mutate} = useSWR<PendingAction[]>(
    token ? [url, token] : null,
    ([u, t]) => api<PendingAction[]>(u, {token: t as string}),
    {refreshInterval: 15000},
  );

  if (!token) return <p className="text-slate-400">Sin sesión</p>;
  if (isLoading) return <p>Cargando…</p>;
  if (error) return <p className="text-rose-400">{String(error)}</p>;
  if (!data || data.length === 0)
    return (
      <div className="text-center py-12">
        <p className="text-slate-400 text-lg">Sin acciones {statusFilter} 🎉</p>
        <p className="text-xs text-slate-500 mt-2">
          Si hay SKUs a pérdida con ad spend, ejecuta el reporte:
        </p>
        <code className="text-xs text-slate-500">POST /api/reports/morning</code>
      </div>
    );

  const tabs = ["pending", "executed", "rejected"];
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {tabs.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 text-xs rounded border uppercase ${
              statusFilter === s
                ? "bg-slate-700 border-slate-500 text-white"
                : "bg-slate-900 border-slate-700 text-slate-400"
            }`}
          >
            {s}
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {data.map((a) => (
          <div
            key={a.id}
            className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase text-slate-400">
                  {a.action_type} · {a.sku ?? "(no sku)"}
                </div>
                <p className="mt-1 text-sm">{a.reasoning}</p>
                {a.whatsapp_message && (
                  <pre className="mt-2 text-xs bg-slate-800 p-2 rounded whitespace-pre-wrap">
                    {a.whatsapp_message}
                  </pre>
                )}
              </div>
              {a.status === "pending" && (
                <ApproveButton actionId={a.id} onResult={() => mutate()} />
              )}
              {a.status !== "pending" && (
                <span className="text-xs uppercase text-slate-400">
                  {a.status}
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500">
              Creado {new Date(a.created_at).toLocaleString()} ·{" "}
              Expira {new Date(a.expires_at).toLocaleString()} ·{" "}
              Confianza {((a.confidence ?? 0) * 100).toFixed(0)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}