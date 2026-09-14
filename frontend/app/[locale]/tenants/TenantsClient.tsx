"use client";
import {useState} from "react";
import useSWR from "swr";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";

interface Tenant {
  id: string;
  name: string;
  source: string;
  locale: string;
  active: boolean;
}

export function TenantsClient() {
  const {token} = useAuth();
  const {data, error, isLoading, mutate} = useSWR<Tenant[]>(
    token ? ["/api/tenants", token] : null,
    ([u, t]) => api<Tenant[]>(u, {token: t as string}),
  );

  const [name, setName] = useState("");
  const [source, setSource] = useState<"shopify" | "woocommerce">("shopify");
  const [busy, setBusy] = useState(false);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    try {
      await api("/api/tenants", {
        method: "POST",
        token,
        body: JSON.stringify({name, source, credentials: {}, settings: {}, locale: "es"}),
      });
      setName("");
      mutate();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={add}
        className="bg-slate-900 border border-slate-800 p-4 rounded-lg flex gap-2 flex-wrap"
      >
        <input
          placeholder="Nombre de la tienda"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="flex-1 px-3 py-2 bg-slate-800 rounded border border-slate-700"
        />
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as "shopify" | "woocommerce")}
          className="px-3 py-2 bg-slate-800 rounded border border-slate-700"
        >
          <option value="shopify">Shopify</option>
          <option value="woocommerce">WooCommerce</option>
        </select>
        <button
          disabled={busy}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded"
        >
          {busy ? "…" : "Crear"}
        </button>
      </form>

      {isLoading && <p>Cargando…</p>}
      {error && <p className="text-rose-400">{String(error)}</p>}
      {data && (
        <div className="space-y-2">
          {data.map((t) => (
            <div
              key={t.id}
              className="bg-slate-900 border border-slate-800 rounded p-3 flex items-center justify-between"
            >
              <div>
                <div className="font-medium">{t.name}</div>
                <div className="text-xs text-slate-400">
                  {t.source} · {t.locale}
                </div>
              </div>
              <span className={t.active ? "text-emerald-400 text-sm" : "text-slate-500 text-sm"}>
                {t.active ? "Activa" : "Inactiva"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}