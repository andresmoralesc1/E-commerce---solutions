"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {api} from "@/lib/api";
import {useAuth} from "@/lib/auth";

interface Props {
  actionId: string;
  onResult?: () => void;
}

export function ApproveButton({actionId, onResult}: Props) {
  const t = useTranslations("actions");
  const {token} = useAuth();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function send(approved: boolean) {
    setBusy(approved ? "approve" : "reject");
    setMsg(null);
    try {
      const r = await api<{ok: boolean; status: string; error?: string}>(
        `/api/agent/confirm/${actionId}`,
        {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({approved}),
        },
      );
      setMsg(r.status);
      onResult?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex gap-2 items-center">
      <button
        onClick={() => send(true)}
        disabled={busy !== null}
        className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs"
      >
        {busy === "approve" ? "…" : t("approve")}
      </button>
      <button
        onClick={() => send(false)}
        disabled={busy !== null}
        className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-xs"
      >
        {busy === "reject" ? "…" : t("reject")}
      </button>
      {msg && <span className="text-xs text-slate-400">{msg}</span>}
    </div>
  );
}