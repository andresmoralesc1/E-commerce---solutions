"use client";
import {useTranslations} from "next-intl";
import type {KPIs} from "@/lib/types";

function fmt(n: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n);
}

export function KPICards({data}: {data: KPIs}) {
  const t = useTranslations("kpi");
  const items = [
    {label: t("revenue"), value: fmt(data.revenue_total), color: "text-emerald-400"},
    {label: t("net_margin"), value: fmt(data.net_margin_total), color: data.net_margin_total >= 0 ? "text-emerald-400" : "text-rose-400"},
    {label: t("ad_spend"), value: fmt(data.ad_spend_total), color: "text-amber-400"},
    {label: t("burning_skus"), value: data.skus_burning, color: data.skus_burning > 0 ? "text-rose-400" : "text-slate-300"},
    {label: t("money_burned"), value: fmt(data.money_burned_3d), color: data.money_burned_3d > 0 ? "text-rose-400" : "text-slate-300"},
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {items.map((it) => (
        <div key={it.label} className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">{it.label}</div>
          <div className={`mt-2 text-2xl font-semibold ${it.color}`}>{it.value}</div>
        </div>
      ))}
    </div>
  );
}