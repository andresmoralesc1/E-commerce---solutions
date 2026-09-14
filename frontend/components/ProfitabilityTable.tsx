"use client";
import {useTranslations} from "next-intl";
import {SemaphoreBadge} from "./SemaphoreBadge";
import type {ProfitabilityRow} from "@/lib/types";

function money(n: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n);
}

export function ProfitabilityTable({rows}: {rows: ProfitabilityRow[]}) {
  const t = useTranslations("products");
  return (
    <div className="overflow-x-auto bg-slate-900 border border-slate-800 rounded-lg">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-800/50 text-slate-300 uppercase text-xs">
          <tr>
            <th className="px-3 py-2 text-left">{t("sku")}</th>
            <th className="px-3 py-2 text-left">{t("title")}</th>
            <th className="px-3 py-2 text-right">{t("stock")}</th>
            <th className="px-3 py-2 text-right">{t("revenue")}</th>
            <th className="px-3 py-2 text-right">{t("margin")}</th>
            <th className="px-3 py-2 text-center">{t("state")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((r) => (
            <tr key={r.product_id} className="hover:bg-slate-800/30">
              <td className="px-3 py-2 font-mono text-xs">{r.sku}</td>
              <td className="px-3 py-2">{r.title || "—"}</td>
              <td className="px-3 py-2 text-right">{r.stock}</td>
              <td className="px-3 py-2 text-right">{money(r.revenue_30d)}</td>
              <td
                className={`px-3 py-2 text-right font-semibold ${
                  r.net_margin_pct > 15
                    ? "text-emerald-400"
                    : r.net_margin_pct > 0
                    ? "text-amber-400"
                    : "text-rose-400"
                }`}
              >
                {r.net_margin_pct.toFixed(1)}%
              </td>
              <td className="px-3 py-2 text-center">
                <SemaphoreBadge state={r.state} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}