"use client";
import {useEffect, useState} from "react";
import useSWR from "swr";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {useTenant} from "@/lib/tenant";
import {ApproveButton} from "@/components/ApproveButton";
import type {PendingAction} from "@/lib/types";

const PAGE_SIZE = 20;

export function PendingClient() {
  const {token} = useAuth();
  const {activeTenantId} = useTenant();
  const [statusFilter, setStatusFilter] = useState("pending");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const base = `/api/agent/pending?status_filter=${statusFilter}&limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`;
  const url = activeTenantId ? `${base}&tenant_id=${activeTenantId}` : base;

  const {data, error, isLoading, mutate} = useSWR<PendingAction[]>(
    token ? [url, token] : null,
    ([u, t]) => api<PendingAction[]>(u, {token: t as string}),
    {refreshInterval: 15000},
  );

  // Reset selection al cambiar de tab o página
  useEffect(() => { setSelected(new Set()); }, [statusFilter, page]);

  async function bulkConfirm(approved: boolean) {
    if (!token || selected.size === 0) return;
    setBulkBusy(true);
    try {
      await api("/api/agent/bulk-confirm", {
        method: "POST",
        token,
        body: JSON.stringify({
          action_ids: Array.from(selected),
          approved,
        }),
      });
      setSelected(new Set());
      mutate();
    } finally {
      setBulkBusy(false);
    }
  }

  function toggleAll() {
    if (!data) return;
    if (selected.size === data.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(data.map((a) => a.id)));
    }
  }

  function toggleOne(id: string) {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    setSelected(n);
  }

  if (!token) return <p className="text-slate-400">Sin sesión</p>;
  if (isLoading) return <p>Cargando…</p>;
  if (error) return <p className="text-rose-400">{String(error)}</p>;

  const tabs = ["pending", "executed", "rejected"];
  const allSelected = data && data.length > 0 && selected.size === data.length;

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center flex-wrap">
        {tabs.map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(0); }}
            className={`px-3 py-1 text-xs rounded border uppercase ${
              statusFilter === s
                ? "bg-slate-700 border-slate-500 text-white"
                : "bg-slate-900 border-slate-700 text-slate-400"
            }`}
          >
            {s}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          {selected.size > 0 && (
            <>
              <span className="text-xs text-slate-400 self-center">
                {selected.size} sel.
              </span>
              <button
                onClick={() => bulkConfirm(true)}
                disabled={bulkBusy}
                className="px-3 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
              >
                Aprobar {selected.size}
              </button>
              <button
                onClick={() => bulkConfirm(false)}
                disabled={bulkBusy}
                className="px-3 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50"
              >
                Rechazar
              </button>
            </>
          )}
        </div>
      </div>

      {!data || data.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-slate-400 text-lg">Sin acciones {statusFilter} 🎉</p>
          <p className="text-xs text-slate-500 mt-2">
            Si hay SKUs a pérdida con ad spend, ejecuta el reporte:
          </p>
          <code className="text-xs text-slate-500">POST /api/reports/morning</code>
        </div>
      ) : (
        <>
          {statusFilter === "pending" && (
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="rounded"
              />
              Seleccionar todas ({data.length})
            </label>
          )}
          <div className="space-y-3">
            {data.map((a) => (
              <div
                key={a.id}
                className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3 flex gap-3"
              >
                {statusFilter === "pending" && (
                  <input
                    type="checkbox"
                    checked={selected.has(a.id)}
                    onChange={() => toggleOne(a.id)}
                    className="mt-1 rounded"
                  />
                )}
                <div className="flex-1">
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
                    {a.status === "pending" ? (
                      <ApproveButton actionId={a.id} onResult={() => mutate()} />
                    ) : (
                      <span className="text-xs uppercase text-slate-400">
                        {a.status}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-2">
                    {new Date(a.created_at).toLocaleString()} ·{" "}
                    Confianza {((a.confidence ?? 0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 justify-center pt-4">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 rounded bg-slate-800 disabled:opacity-30 text-sm"
            >
              ← Anterior
            </button>
            <span className="text-xs text-slate-400 self-center">
              Página {page + 1}
            </span>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!data || data.length < PAGE_SIZE}
              className="px-3 py-1 rounded bg-slate-800 disabled:opacity-30 text-sm"
            >
              Siguiente →
            </button>
          </div>
        </>
      )}
    </div>
  );
}