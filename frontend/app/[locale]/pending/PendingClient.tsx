"use client";
import useSWR from "swr";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";
import {ApproveButton} from "@/components/ApproveButton";
import type {PendingAction} from "@/lib/types";

export function PendingClient() {
  const {token} = useAuth();
  const {data, error, isLoading, mutate} = useSWR<PendingAction[]>(
    token ? ["/api/agent/pending?status_filter=pending", token] : null,
    ([u, t]) => api<PendingAction[]>(u, {token: t as string}),
    {refreshInterval: 15000},
  );

  if (!token) return <p className="text-slate-400">Sin sesión</p>;
  if (isLoading) return <p>Cargando…</p>;
  if (error) return <p className="text-rose-400">{String(error)}</p>;
  if (!data || data.length === 0)
    return <p className="text-slate-400">Sin acciones pendientes 🎉</p>;

  return (
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
            <ApproveButton actionId={a.id} onResult={() => mutate()} />
          </div>
          <div className="text-xs text-slate-500">
            Creado {new Date(a.created_at).toLocaleString()} ·{" "}
            Expira {new Date(a.expires_at).toLocaleString()} ·{" "}
            Confianza {((a.confidence ?? 0) * 100).toFixed(0)}%
          </div>
        </div>
      ))}
    </div>
  );
}