"use client";
import {useTranslations} from "next-intl";
import type {SKUState} from "@/lib/types";

const COLORS: Record<SKUState, string> = {
  GANADOR: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  A_OPTIMIZAR: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
  EN_RIESGO: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  A_PERDIDA: "bg-rose-500/20 text-rose-300 border-rose-500/40",
};

export function SemaphoreBadge({state}: {state: SKUState}) {
  const t = useTranslations("products.states");
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs border ${COLORS[state]}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {t(state)}
    </span>
  );
}