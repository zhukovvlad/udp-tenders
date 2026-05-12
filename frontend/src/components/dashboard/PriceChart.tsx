import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { ChartContainer } from "@/components/ui/chart";
import type { DashboardCalculation } from "@/types/dashboard";
import { formatMoney } from "@/lib/format";

interface Props {
  calculations: DashboardCalculation[];
}

export function PriceChart({ calculations }: Props) {
  if (!calculations.length) return (
    <div className="flex h-48 items-center justify-center text-sm text-fg-tertiary">
      Рассчитайте отклонения по объектам, чтобы увидеть динамику
    </div>
  );

  const classNames = [...new Set(calculations.map((c) => c.material_class_name).filter(Boolean))] as string[];
  const byPeriod = new Map<string, Record<string, number>>();
  calculations.forEach((c) => {
    if (!c.period_start || !c.material_class_name) return;
    if (!byPeriod.has(c.period_start)) byPeriod.set(c.period_start, {});
    byPeriod.get(c.period_start)![c.material_class_name] = c.avg_price;
  });
  const data = [...byPeriod.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([period, values]) => ({ period, ...values }));

  const COLORS = ["#9CC79A", "#EFB75C", "#F0B0A0", "#7DA876", "#C8E0C2"];

  return (
    <ChartContainer config={{}}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => (typeof v === "number" ? formatMoney(v) : String(v))} tick={{ fontSize: 11 }} width={80} />
        <Tooltip formatter={(v) => (typeof v === "number" ? formatMoney(v) : String(v ?? "—"))} />
        <Legend />
        {classNames.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            dot={false}
            strokeWidth={1.5}
          />
        ))}
      </LineChart>
    </ChartContainer>
  );
}
