"use client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from "recharts";
import type {ProfitabilityRow} from "@/lib/types";

function money(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}

const COLORS: Record<string, string> = {
  GANADOR: "#10b981",
  A_OPTIMIZAR: "#eab308",
  EN_RIESGO: "#f97316",
  A_PERDIDA: "#f43f5e",
};

export function StateDistributionChart({rows}: {rows: ProfitabilityRow[]}) {
  const counts = rows.reduce((acc, r) => {
    acc[r.state] = (acc[r.state] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const data = Object.entries(counts).map(([state, count]) => ({
    state,
    count,
    fill: COLORS[state] ?? "#6b7280",
  }));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm uppercase text-slate-400 mb-2">Distribución por estado</h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="state"
            cx="50%"
            cy="50%"
            outerRadius={70}
            label={(e: any) => `${e.state}: ${e.count}`}
          />
          <Tooltip
            contentStyle={{background: "#0f172a", border: "1px solid #334155"}}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AdSpendVsRevenueChart({rows}: {rows: ProfitabilityRow[]}) {
  const top = [...rows]
    .sort((a, b) => Math.abs(b.net_margin_abs) - Math.abs(a.net_margin_abs))
    .slice(0, 10);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm uppercase text-slate-400 mb-2">
        Top 10 SKUs: Revenue vs Ad Spend
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={top} margin={{left: 10, right: 10}}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="sku"
            tick={{fill: "#94a3b8", fontSize: 10}}
            angle={-30}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{fill: "#94a3b8", fontSize: 10}} tickFormatter={money} />
          <Tooltip
            contentStyle={{background: "#0f172a", border: "1px solid #334155"}}
            formatter={(v: number) => money(v)}
          />
          <Bar dataKey="revenue_30d" fill="#10b981" name="Revenue" />
          <Bar dataKey="ad_spend_total" fill="#f43f5e" name="Ad spend" />
          <Bar dataKey="net_margin_abs" fill="#3b82f6" name="Net margin" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MarginPctChart({rows}: {rows: ProfitabilityRow[]}) {
  const data = [...rows]
    .sort((a, b) => a.net_margin_pct - b.net_margin_pct)
    .slice(0, 15)
    .map((r) => ({
      sku: r.sku.slice(0, 14),
      margin: r.net_margin_pct,
      fill: COLORS[r.state] ?? "#6b7280",
    }));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm uppercase text-slate-400 mb-2">
        Top 15 SKUs con peor margen %
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} layout="vertical" margin={{left: 10}}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis type="number" tick={{fill: "#94a3b8", fontSize: 10}} tickFormatter={(v) => `${v.toFixed(0)}%`} />
          <YAxis dataKey="sku" type="category" tick={{fill: "#94a3b8", fontSize: 10}} width={90} />
          <Tooltip
            contentStyle={{background: "#0f172a", border: "1px solid #334155"}}
            formatter={(v: number) => `${v.toFixed(1)}%`}
          />
          <Bar dataKey="margin">
            {data.map((entry, idx) => (
              <Cell key={idx} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}