"use client";
import {useState, useEffect} from "react";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";

interface Tenant {
  id: string;
  name: string;
  source: string;
  active: boolean;
}

type Step = 1 | 2 | 3 | 4 | 5;

const STEPS = [
  {n: 1, title: "Crear tienda", description: "Crea tu primera tienda (Shopify o WooCommerce)"},
  {n: 2, title: "Conectar credenciales", description: "Shopify token o Woo consumer keys"},
  {n: 3, title: "Sincronizar datos", description: "Pull inicial de pedidos y productos"},
  {n: 4, title: "Conectar Ads", description: "Meta y/o Google para pausar/escalar campañas"},
  {n: 5, title: "WhatsApp", description: "Evolution API para alertas al celular"},
] as const;

export function OnboardingWizard({locale}: {locale: string}) {
  const {token} = useAuth();
  const [step, setStep] = useState<Step>(1);
  const [completed, setCompleted] = useState<Set<Step>>(new Set());
  const [tenants, setTenants] = useState<Tenant[]>([]);

  useEffect(() => {
    if (!token) return;
    const stored = localStorage.getItem("brain_onboarding");
    if (stored) {
      try {
        const data = JSON.parse(stored);
        setCompleted(new Set(data.completed ?? []));
        if (data.step) setStep(data.step);
      } catch {}
    }
    api<Tenant[]>("/api/tenants", {token}).then(setTenants).catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!token) return;
    localStorage.setItem(
      "brain_onboarding",
      JSON.stringify({step, completed: Array.from(completed)}),
    );
  }, [step, completed, token]);

  function markDone(s: Step) {
    const n = new Set(completed);
    n.add(s);
    setCompleted(n);
    if (s < 5) setStep(((s + 1) as Step));
  }

  function dismiss() {
    localStorage.removeItem("brain_onboarding");
    setStep(1);
    setCompleted(new Set([1, 2, 3, 4, 5]));
  }

  const allDone = completed.size === 5;

  if (allDone) {
    return (
      <div className="bg-emerald-900/30 border border-emerald-700/50 rounded-lg p-4 text-sm text-emerald-200">
        ✅ Onboarding completo.{" "}
        <button onClick={dismiss} className="underline ml-2">
          Repetir tour
        </button>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">🚀 Onboarding</h2>
        <button onClick={dismiss} className="text-xs text-slate-500 hover:text-slate-300">
          Saltar todo
        </button>
      </div>

      {/* Steps indicator */}
      <div className="flex gap-2 mb-4 overflow-x-auto">
        {STEPS.map((s) => (
          <button
            key={s.n}
            onClick={() => setStep(s.n as Step)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs whitespace-nowrap ${
              step === s.n
                ? "bg-emerald-500 text-white"
                : completed.has(s.n as Step)
                ? "bg-emerald-900/40 text-emerald-300 border border-emerald-700/40"
                : "bg-slate-800 text-slate-400"
            }`}
          >
            {completed.has(s.n as Step) ? "✓" : s.n}
            <span>{s.title}</span>
          </button>
        ))}
      </div>

      {/* Step content */}
      {step === 1 && <Step1 onDone={() => markDone(1)} token={token!} />}
      {step === 2 && <Step2 onDone={() => markDone(2)} tenants={tenants} />}
      {step === 3 && <Step3 onDone={() => markDone(3)} tenants={tenants} token={token!} />}
      {step === 4 && <Step4 onDone={() => markDone(4)} />}
      {step === 5 && <Step5 onDone={() => markDone(5)} locale={locale} />}
    </div>
  );
}

function Step1({onDone, token}: {onDone: () => void; token: string}) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<"shopify" | "woocommerce">("shopify");
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!name) return;
    setBusy(true);
    try {
      await api("/api/tenants", {
        method: "POST",
        token,
        body: JSON.stringify({
          name,
          source,
          credentials: {},
          settings: {currency: "COP"},
          locale: "es",
        }),
      });
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Crea tu primera tienda</h3>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Mi Tienda"
        className="w-full px-3 py-2 bg-slate-800 rounded border border-slate-700"
      />
      <select
        value={source}
        onChange={(e) => setSource(e.target.value as any)}
        className="px-3 py-2 bg-slate-800 rounded border border-slate-700"
      >
        <option value="shopify">Shopify</option>
        <option value="woocommerce">WooCommerce</option>
      </select>
      <button
        onClick={create}
        disabled={!name || busy}
        className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded"
      >
        {busy ? "..." : "Crear tienda"}
      </button>
    </div>
  );
}

function Step2({onDone, tenants}: {onDone: () => void; tenants: Tenant[]}) {
  if (tenants.length === 0) {
    return (
      <div>
        <p className="text-amber-400">Primero crea una tienda en el paso 1.</p>
        <button onClick={onDone} className="mt-2 text-xs text-slate-400 underline">
          Marcar listo (no usar)
        </button>
      </div>
    );
  }
  const t = tenants[0];
  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Conecta credenciales de {t.name}</h3>
      <p className="text-sm text-slate-400">
        Ve a <code className="bg-slate-800 px-1 rounded">/es/tenants</code>,
        edita el tenant para configurar shop_domain + access_token (Shopify)
        o site_url + consumer_key/secret (WooCommerce).
      </p>
      <p className="text-xs text-slate-500">
        Ver guía paso-a-paso en <code>docs/SHOPIFY.md</code> o <code>docs/WOOCOMMERCE.md</code>.
      </p>
      <button onClick={onDone} className="px-4 py-2 bg-emerald-500 rounded">
        Listo, sigo
      </button>
    </div>
  );
}

function Step3({onDone, tenants, token}: {onDone: () => void; tenants: Tenant[]; token: string}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function sync() {
    if (!tenants[0]) return;
    setBusy(true);
    try {
      const endpoint = `/api/sync/${tenants[0].source}/${tenants[0].id}/now`;
      const r = await api(endpoint, {method: "POST", token});
      setResult(r);
      onDone();
    } catch (e) {
      setResult({error: String(e)});
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Sincroniza tus primeros pedidos</h3>
      {tenants[0] ? (
        <>
          <p className="text-sm text-slate-400">
            Pull inicial de <strong>{tenants[0].name}</strong> ({tenants[0].source}).
            Si no tienes credenciales reales aún, prueba con datos demo:
          </p>
          <pre className="bg-slate-800 p-2 rounded text-xs overflow-x-auto">
            docker compose exec backend python scripts/seed_demo.py
          </pre>
          <button
            onClick={sync}
            disabled={busy}
            className="px-4 py-2 bg-emerald-500 rounded"
          >
            {busy ? "Sincronizando..." : "Sincronizar ahora"}
          </button>
          {result && (
            <pre className="bg-slate-800 p-2 rounded text-xs overflow-x-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </>
      ) : (
        <p className="text-amber-400">Crea una tienda primero.</p>
      )}
    </div>
  );
}

function Step4({onDone}: {onDone: () => void}) {
  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Conecta Meta + Google Ads</h3>
      <p className="text-sm text-slate-400">
        Cuando estés listo para conectar cuentas reales de ads:
      </p>
      <ol className="text-xs space-y-2 list-decimal list-inside text-slate-300">
        <li>Configura META_APP_ID/SECRET y GOOGLE_CLIENT_ID/SECRET en .env</li>
        <li>Reinicia backend: <code className="bg-slate-800 px-1 rounded">docker compose restart backend</code></li>
        <li>
          Abre{" "}
          <a
            href="/api/auth/meta/start?tenant_id="
            target="_blank"
            className="text-emerald-400 underline"
          >
            /api/auth/meta/start
          </a>{" "}
          para OAuth Meta (repite con /api/auth/google/start)
        </li>
        <li>Una vez conectado, /agent/decide puede pausar campañas reales</li>
      </ol>
      <p className="text-xs text-slate-500">
        Mientras tanto, el sistema funciona en modo "noop_no_creds" — solo detecta
        decisiones sin ejecutar.
      </p>
      <button onClick={onDone} className="px-4 py-2 bg-emerald-500 rounded">
        Entendido
      </button>
    </div>
  );
}

function Step5({onDone, locale}: {onDone: () => void; locale: string}) {
  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Activa WhatsApp (opcional)</h3>
      <p className="text-sm text-slate-400">
        Recibe alertas en tu celular y responde SI/NO para aprobar acciones.
      </p>
      <ol className="text-xs space-y-2 list-decimal list-inside text-slate-300">
        <li>
          <code className="bg-slate-800 px-1 rounded">docker compose --profile phase4 up -d evolution evolution-db</code>
        </li>
        <li>Crear instancia + escanear QR (ver docs/EVOLUTION.md)</li>
        <li>
          Configurar <code className="bg-slate-800 px-1 rounded">manager_phone</code> del tenant en la DB
        </li>
        <li>Importar workflow 06-morning-whatsapp-8am en n8n</li>
      </ol>
      <button onClick={onDone} className="px-4 py-2 bg-emerald-500 rounded">
        Lo configuraré luego
      </button>
    </div>
  );
}