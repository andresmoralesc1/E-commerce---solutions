"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";

export function LoginForm({locale}: {locale: string}) {
  const t = useTranslations("auth");
  const router = useRouter();
  const {setToken} = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const body = new URLSearchParams({username: email, password});
      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body,
      });
      if (!r.ok) {
        setErr("Credenciales inválidas");
        return;
      }
      const data = (await r.json()) as {access_token: string};
      setToken(data.access_token);
      router.push(`/${locale}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="w-full max-w-sm bg-slate-900 border border-slate-800 p-6 rounded-lg space-y-4"
    >
      <h1 className="text-xl font-semibold text-emerald-400">🧠 Ecommerce Brain</h1>
      <p className="text-sm text-slate-400">Inicia sesión</p>
      <div>
        <label className="block text-xs uppercase text-slate-400 mb-1">
          {t("email")}
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 rounded border border-slate-700 focus:border-emerald-500 outline-none"
        />
      </div>
      <div>
        <label className="block text-xs uppercase text-slate-400 mb-1">
          {t("password")}
        </label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 rounded border border-slate-700 focus:border-emerald-500 outline-none"
        />
      </div>
      {err && <p className="text-rose-400 text-sm">{err}</p>}
      <button
        type="submit"
        disabled={busy}
        className="w-full py-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 rounded font-medium"
      >
        {busy ? "…" : t("submit")}
      </button>
    </form>
  );
}