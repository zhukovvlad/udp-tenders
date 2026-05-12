import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell,
} from "recharts";
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

  const data = calculations
    .filter((c) => c.avg_price > 0)
    .map((c) => ({
      name: c.material_class_name ?? "?",
      avg: c.avg_price,
      ref: c.reference_price ?? null,
      deviation_pct: c.deviation_pct ?? 0,
    }));

  return (
    <ChartContainer config={{}} className="h-[220px] w-full">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis
          tickFormatter={(v) => (typeof v === "number" ? formatMoney(v) : String(v))}
          tick={{ fontSize: 11 }}
          width={90}
        />
        <Tooltip
          formatter={(v, name) => [
            typeof v === "number" ? formatMoney(v) : "—",
            name === "avg" ? "Средняя цена" : "Эталон",
          ]}
        />
        <Legend formatter={(v) => (v === "avg" ? "Средняя цена" : "Эталон")} />
        <Bar dataKey="avg" name="avg" radius={[3, 3, 0, 0]}>
          {data.map((entry) => (
            <Cell
              key={entry.name}
              fill={
                !entry.ref
                  ? "#9CA39A"
                  : entry.deviation_pct > 0
                  ? "#D85A30"
                  : "#9CC79A"
              }
            />
          ))}
        </Bar>
        <Bar dataKey="ref" name="ref" radius={[3, 3, 0, 0]} fill="rgba(255,255,255,0.15)" />
      </BarChart>
    </ChartContainer>
  );
}
