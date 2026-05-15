import { Bar, BarChart, Cell, LabelList, ReferenceLine, XAxis, YAxis } from "recharts";
import type { LabelProps } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { DashboardCalculation } from "@/types/dashboard";
import { formatDate, formatMoney } from "@/lib/format";

interface Props {
  calculations: DashboardCalculation[];
  onConfigurePrice?: () => void;
}

function fillFor(pct: number): string {
  if (pct > 2) return "#D85A30";
  if (pct > 0) return "#EFB75C";
  return "#9CC79A";
}

const chartConfig = {
  value: { label: "Отклонение" },
} satisfies ChartConfig;

// Custom label: renders coloured % text after each bar
function PctLabel(props: LabelProps) {
  const x = Number(props.x ?? 0);
  const y = Number(props.y ?? 0);
  const width = Number(props.width ?? 0);
  const height = Number(props.height ?? 0);
  const value = Number(props.value ?? 0);

  const color = value > 2 ? "#F0B0A0" : value > 0 ? "#EFB75C" : "#9CC79A";
  const label = `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  // recharts passes negative width for negative bars: x = zero-axis, x+width = bar tip (left)
  // Use min/max to find real bar edges regardless of sign.
  const barLeft = Math.min(x, x + width);
  const barRight = Math.max(x, x + width);
  const labelX = value >= 0 ? barRight + 6 : barLeft - 6;
  const anchor = value >= 0 ? "start" : "end";

  return (
    <text
      x={labelX}
      y={y + height / 2}
      textAnchor={anchor}
      dominantBaseline="central"
      fontSize={12}
      fontWeight={500}
      fill={color}
    >
      {label}
    </text>
  );
}

export function DeviationChart({ calculations, onConfigurePrice }: Props) {
  if (!calculations.length) return null;

  // When auto-calculate runs it creates monthly rows; show only the latest period.
  const latestPeriodEnd = calculations.reduce(
    (max, c) => (c.period_end > max ? c.period_end : max),
    calculations[0].period_end,
  );
  const latestPeriodCalcs = calculations.filter(
    (c) => c.period_end === latestPeriodEnd,
  );

  // deviation_pct is null when reference_price is null or <= 0 (see crud.recalculate_prices)
  const withPrice = latestPeriodCalcs.filter((c) => c.deviation_pct !== null);
  const withoutPrice = latestPeriodCalcs.filter((c) => c.deviation_pct === null);

  const latestPeriodStart = latestPeriodCalcs.reduce(
    (min, c) => (c.period_start < min ? c.period_start : min),
    latestPeriodCalcs[0].period_start,
  );
  const latestPeriodLabelEnd = latestPeriodCalcs.reduce(
    (max, c) => (c.period_end > max ? c.period_end : max),
    latestPeriodCalcs[0].period_end,
  );
  const periodLabel =
    latestPeriodStart && latestPeriodLabelEnd
      ? `${formatDate(latestPeriodStart)} — ${formatDate(latestPeriodLabelEnd)}`
      : null;

  const maxAbsPct = withPrice.length
    ? Math.max(...withPrice.map((c) => Math.abs(c.deviation_pct!)), 0.5)
    : 5;
  const domainBound = Math.ceil(maxAbsPct * 1.5);

  const data = withPrice.map((c) => ({
    name: c.material_class_name,
    value: c.deviation_pct!,
    amount: c.deviation_amount,
    fill: fillFor(c.deviation_pct!),
  }));

  const chartHeight = withPrice.length * 36 + 8;

  return (
    <div className="rounded-xl border border-border-subtle bg-surface p-5 space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <h2 className="text-sm font-medium">Отклонения по классам бетона</h2>
          {periodLabel && (
            <span className="text-xs text-fg-tertiary">{periodLabel}</span>
          )}
        </div>
        <span className="shrink-0 text-xs text-fg-tertiary">относительно плановой цены</span>
      </div>

      {withPrice.length > 0 && (
        <ChartContainer
          config={chartConfig}
          className="w-full"
          style={{ height: chartHeight }}
        >
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 0, right: 56, left: 40, bottom: 0 }}
            barSize={8}
            barCategoryGap="40%"
          >
            <YAxis
              dataKey="name"
              type="category"
              tickLine={false}
              axisLine={false}
              width={48}
              tick={{ fontSize: 13, fontWeight: 500, fill: "currentColor" }}
            />
            <XAxis
              type="number"
              domain={[-domainBound, domainBound]}
              hide
            />
            <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" strokeWidth={1} />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  formatter={(value, _name, item) => {
                    const v = Number(value);
                    const pctStr = `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
                    const amtStr =
                      item.payload?.amount != null
                        ? `  (${formatMoney(item.payload.amount)})`
                        : "";
                    return pctStr + amtStr;
                  }}
                  hideLabel
                />
              }
            />
            <Bar dataKey="value" radius={4}>
              {data.map((entry, idx) => (
                <Cell key={`${entry.name}-${idx}`} fill={entry.fill} />
              ))}
              <LabelList dataKey="value" content={PctLabel} />
            </Bar>
          </BarChart>
        </ChartContainer>
      )}

      {withoutPrice.map((c, idx) => (
        <div key={`${c.material_class_name}-${idx}`} className="flex items-center gap-3.5">
          <div className="w-12 shrink-0 text-sm font-medium text-fg-tertiary">
            {c.material_class_name}
          </div>
          <div className="h-2 flex-1 rounded-full bg-surface-hover" />
          {typeof onConfigurePrice === "function" ? (
            <button
              type="button"
              onClick={onConfigurePrice}
              className="shrink-0 text-right text-xs italic text-accent-text hover:underline"
            >
              Нет плановой цены · настроить →
            </button>
          ) : (
            <span className="shrink-0 text-right text-xs italic text-fg-tertiary">
              Нет плановой цены
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
