import {
  BarChart, Bar, XAxis, YAxis, ReferenceLine, Tooltip, Cell,
} from "recharts";
import { ChartContainer } from "@/components/ui/chart";
import type { DashboardCalculation } from "@/types/dashboard";

interface Props {
  calculations: DashboardCalculation[];
}

export function DeviationChart({ calculations }: Props) {
  if (!calculations.length) return null;

  const data = calculations.map((c) => ({
    name: c.material_class_name,
    value: c.deviation_pct ?? 0,
  }));

  return (
    <ChartContainer config={{}} className="h-[180px] w-full">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11 }} width={40} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.2)" />
        <Tooltip formatter={(v) => (typeof v === "number" ? `${v.toFixed(2)}%` : String(v))} />
        <Bar dataKey="value" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell
              key={`${entry.name ?? "unknown"}-${i}`}
              fill={entry.value > 0 ? "#D85A30" : "#9CC79A"}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
