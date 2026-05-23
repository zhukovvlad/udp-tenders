import { useState } from "react";
import { Bar, BarChart, Cell, ReferenceLine, XAxis, YAxis } from "recharts";
import type { LabelProps } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui-domain/Button";
import { AlertTriangle } from "lucide-react";
import type { DashboardCalculation } from "@/types/dashboard";
import { formatDate, formatMoney, pluralRu } from "@/lib/format";


interface Props {
  calculations: DashboardCalculation[];
  periodFilterActive?: boolean;
  onConfigurePrice?: () => void;
  /** Period filter state — if provided, filter inputs are rendered in the chart header */
  periodStart?: string;
  periodEnd?: string;
  dataStart?: string;
  dataEnd?: string;
  displayStart?: string;
  displayEnd?: string;
  onPeriodStartChange?: (v: string) => void;
  onPeriodEndChange?: (v: string) => void;
  onPeriodReset?: () => void;
}

function fillFor(pct: number): string {
  if (pct > 2) return "#D85A30";
  if (pct > 0) return "#EFB75C";
  return "#9CC79A";
}

const chartConfig = {
  value: { label: "Отклонение" },
} satisfies ChartConfig;

// Custom label: renders "+4.0% · +112 000 ₽" after each bar in a single <text>
interface BarLabelProps extends LabelProps {
  amount?: number | null;
}
function BarLabel(props: BarLabelProps) {
  const x = Number(props.x ?? 0);
  const y = Number(props.y ?? 0);
  const width = Number(props.width ?? 0);
  const height = Number(props.height ?? 0);
  const pct = Number(props.value ?? 0);
  const amount = props.amount ?? null;

  const color = pct > 2 ? "#F0B0A0" : pct > 0 ? "#EFB75C" : "#9CC79A";
  const pctStr = `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
  const amtStr = amount != null
    ? `  ·  ${amount > 0 ? "+" : ""}${formatMoney(Math.abs(amount))}`
    : "";

  // recharts passes negative width for negative bars: x = zero-axis, x+width = bar tip (left)
  const barLeft = Math.min(x, x + width);
  const barRight = Math.max(x, x + width);
  const labelX = pct >= 0 ? barRight + 6 : barLeft - 6;
  const anchor = pct >= 0 ? "start" : "end";

  return (
    <text
      x={labelX}
      y={y + height / 2}
      textAnchor={anchor}
      dominantBaseline="central"
      fontSize={12}
    >
      <tspan fontWeight={500} fill={color}>{pctStr}</tspan>
      {amtStr && (
        <tspan fill="rgba(180,176,168,0.7)">{amtStr}</tspan>
      )}
    </text>
  );
}

interface FilterHeaderProps {
  periodStart: string;
  periodEnd: string;
  dataStart?: string;
  dataEnd?: string;
  onPeriodStartChange: (v: string) => void;
  onPeriodEndChange: (v: string) => void;
  onPeriodReset?: () => void;
}

function FilterHeader({
  periodStart,
  periodEnd,
  dataStart,
  dataEnd,
  onPeriodStartChange,
  onPeriodEndChange,
  onPeriodReset,
}: FilterHeaderProps) {
  const [startInvalid, setStartInvalid] = useState(false);
  const [endInvalid, setEndInvalid] = useState(false);

  // badInput is true when the browser has partial/impossible input it can't parse
  // as a date (e.g. April 31 — browser sets value="" but badInput=true).
  // el.value !== "" alone would never catch these because the browser sanitizes
  // the value to "" for impossible dates. onInput fires on every segment keystroke —
  // onChange alone misses it because React deduplicates when value stays "".
  const isFieldInvalid = (el: HTMLInputElement) => el.validity.badInput;

  function handleStartChange(e: React.ChangeEvent<HTMLInputElement>) {
    const invalid = isFieldInvalid(e.target);
    setStartInvalid(invalid);
    // Don't propagate invalid (empty) value so the parent keeps its previous valid date
    if (!invalid) onPeriodStartChange(e.target.value);
  }
  function handleEndChange(e: React.ChangeEvent<HTMLInputElement>) {
    const invalid = isFieldInvalid(e.target);
    setEndInvalid(invalid);
    if (!invalid) onPeriodEndChange(e.target.value);
  }
  // onInput fires on every segment keystroke — onChange alone misses it because
  // React deduplicates when e.target.value stays "" throughout invalid typing.
  function handleStartInput(e: React.SyntheticEvent<HTMLInputElement>) {
    setStartInvalid(isFieldInvalid(e.currentTarget));
  }
  function handleEndInput(e: React.SyntheticEvent<HTMLInputElement>) {
    setEndInvalid(isFieldInvalid(e.currentTarget));
  }
  function handleStartBlur(e: React.FocusEvent<HTMLInputElement>) {
    setStartInvalid(isFieldInvalid(e.target));
  }
  function handleEndBlur(e: React.FocusEvent<HTMLInputElement>) {
    setEndInvalid(isFieldInvalid(e.target));
  }
  function handleReset() {
    setStartInvalid(false);
    setEndInvalid(false);
    onPeriodReset?.();
  }

  const hasError = startInvalid || endInvalid;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-border-subtle">
      <div>
        <div className="text-sm font-medium">Отклонения по классам бетона</div>
        <div className="text-xs text-fg-tertiary mt-0.5">относительно плановой цены</div>
      </div>
      <div className="flex flex-col items-end gap-2">
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={periodStart}
            placeholder={dataStart}
            onChange={handleStartChange}
            onInput={handleStartInput}
            onBlur={handleStartBlur}
            aria-invalid={startInvalid || undefined}
            className="w-36 text-xs"
            style={startInvalid ? { borderColor: "var(--color-destructive)", boxShadow: "0 0 0 1px var(--color-destructive)" } : undefined}
            data-testid="period-start-input"
          />
          {startInvalid && (
            <AlertTriangle aria-hidden size={14} className="shrink-0 text-destructive" />
          )}
          <span className="text-xs text-fg-tertiary">—</span>
          <Input
            type="date"
            value={periodEnd}
            placeholder={dataEnd}
            onChange={handleEndChange}
            onInput={handleEndInput}
            onBlur={handleEndBlur}
            aria-invalid={endInvalid || undefined}
            className="w-36 text-xs"
            style={endInvalid ? { borderColor: "var(--color-destructive)", boxShadow: "0 0 0 1px var(--color-destructive)" } : undefined}
            data-testid="period-end-input"
          />
          {endInvalid && (
            <AlertTriangle aria-hidden size={14} className="shrink-0 text-destructive" />
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleReset}
            disabled={!periodStart && !periodEnd}
            data-testid="period-reset-button"
          >
            Сбросить
          </Button>
        </div>
        {hasError && (
          <div
            role="alert"
            aria-live="polite"
            className="flex items-center gap-1.5 rounded-md border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive"
          >
            <AlertTriangle aria-hidden size={12} />
            Некорректная дата — фильтр не применён
          </div>
        )}
      </div>
    </div>
  );
}

export function DeviationChart({
  calculations,
  periodFilterActive = false,
  onConfigurePrice,
  periodStart = "",
  periodEnd = "",
  dataStart,
  dataEnd,
  displayStart,
  displayEnd,
  onPeriodStartChange,
  onPeriodEndChange,
  onPeriodReset,
}: Props) {
  const hasFilterProps = typeof onPeriodStartChange === "function" && typeof onPeriodEndChange === "function";

  if (!calculations.length) {
    // Still render the card shell with filter inputs when the parent controls the filter
    if (!hasFilterProps) return null;
    return (
      <div className="rounded-xl border border-border-subtle bg-surface overflow-hidden">
        <FilterHeader
          periodStart={periodStart}
          periodEnd={periodEnd}
          dataStart={dataStart}
          dataEnd={dataEnd}
          onPeriodStartChange={onPeriodStartChange}
          onPeriodEndChange={onPeriodEndChange!}
          onPeriodReset={onPeriodReset}
        />
        <div className="px-5 py-10 text-center text-sm text-fg-tertiary">
          Нет данных за выбранный период
        </div>
      </div>
    );
  }

  // When a period filter is active — aggregate all months by material class.
  // Otherwise — show only the latest calendar month in the data.
  const displayCalcs: DashboardCalculation[] = periodFilterActive
    ? (() => {
        const byClass = new Map<number, DashboardCalculation[]>();
        for (const c of calculations) {
          if (!byClass.has(c.material_class_id)) byClass.set(c.material_class_id, []);
          byClass.get(c.material_class_id)!.push(c);
        }
        return Array.from(byClass.values()).map((rows) => {
          const totalQty = rows.reduce((s, r) => s + (r.total_qty ?? 0), 0);
          const deviationAmount = rows.every((r) => r.deviation_amount === null)
            ? null
            : rows.reduce((s, r) => s + (r.deviation_amount ?? 0), 0);
          // Derive % from totals to avoid double-counting when reference prices vary across months.
          // Null when any included row lacks a usable reference price (null or <= 0).
          const refQtyTotal = rows.every((r) => r.reference_price !== null && r.reference_price > 0)
            ? rows.reduce((s, r) => s + (r.reference_price! * (r.total_qty ?? 0)), 0)
            : null;
          const deviationPct =
            deviationAmount !== null && refQtyTotal !== null && refQtyTotal > 0
              ? (deviationAmount / refQtyTotal) * 100
              : null;
          const totalMaterial = rows.reduce((s, r) => s + (r.material_total ?? 0), 0);
          const totalDelivery = rows.reduce((s, r) => s + (r.delivery_total ?? 0), 0);
          const avgPrice = totalQty > 0 ? (totalMaterial + totalDelivery) / totalQty : 0;
          // reference_price: weighted average when all months have a usable price, else null.
          const referencePrice = rows.every((r) => r.reference_price !== null && r.reference_price > 0)
            ? refQtyTotal! / totalQty
            : null;
          return {
            ...rows[0],
            period_start: rows.reduce((m, r) => (r.period_start < m ? r.period_start : m), rows[0].period_start),
            period_end: rows.reduce((m, r) => (r.period_end > m ? r.period_end : m), rows[0].period_end),
            total_qty: totalQty,
            material_total: totalMaterial,
            delivery_total: totalDelivery,
            avg_price: avgPrice,
            reference_price: referencePrice,
            deviation_amount: deviationAmount,
            deviation_pct: deviationPct,
          };
        });
      })()
    : (() => {
        const latestPeriodEnd = calculations.reduce(
          (max, c) => (c.period_end > max ? c.period_end : max),
          calculations[0].period_end,
        );
        return calculations.filter((c) => c.period_end === latestPeriodEnd);
      })();

  // deviation_pct is null when reference_price is null or <= 0
  const withPrice = displayCalcs.filter((c) => c.deviation_pct !== null);
  const withoutPrice = displayCalcs.filter((c) => c.deviation_pct === null);

  const anyHasDeviation = displayCalcs.some((c) => c.deviation_amount !== null);
  const totalBannerDev = anyHasDeviation
    ? displayCalcs.reduce((s, c) => s + (c.deviation_amount ?? 0), 0)
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
    <div className="rounded-xl border border-border-subtle bg-surface overflow-hidden">
      {/* ── Header: title + period filter ── */}
      {hasFilterProps ? (
        <FilterHeader
          periodStart={periodStart}
          periodEnd={periodEnd}
          dataStart={dataStart}
          dataEnd={dataEnd}
          onPeriodStartChange={onPeriodStartChange!}
          onPeriodEndChange={onPeriodEndChange!}
          onPeriodReset={onPeriodReset}
        />
      ) : (
        <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-border-subtle">
          <div>
            <div className="text-sm font-medium">Отклонения по классам бетона</div>
            <div className="text-xs text-fg-tertiary mt-0.5">относительно плановой цены</div>
          </div>
        </div>
      )}

      {/* ── Period summary banner ── */}
      {totalBannerDev !== null && (
        <div
          className={
            totalBannerDev > 0
              ? "flex items-center justify-between px-5 py-3 bg-danger-soft border-b border-danger-border"
              : "flex items-center justify-between px-5 py-3 bg-accent-soft border-b border-accent-border"
          }
        >
          <span className="text-xs text-fg-secondary">
            За выбранный период
            {displayStart && displayEnd
              ? ` (${formatDate(displayStart)} — ${formatDate(displayEnd)})`
              : ""}
          </span>
          <span
            className={
              "text-sm font-medium " +
              (totalBannerDev > 0 ? "text-danger-text" : "text-accent-text")
            }
          >
            {totalBannerDev > 0
              ? `Переплата: +${formatMoney(totalBannerDev)}`
              : `Экономия: ${formatMoney(Math.abs(totalBannerDev))}`}
          </span>
        </div>
      )}

      {/* ── Chart bars ── */}
      {withPrice.length > 0 && (
        <div className="p-5">
          <ChartContainer
            config={chartConfig}
            className="w-full"
            style={{ height: chartHeight }}
          >
            <BarChart
              layout="vertical"
              data={data}
              margin={{ top: 0, right: 140, left: 40, bottom: 0 }}
              barSize={16}
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
              <Bar
                dataKey="value"
                radius={4}
                label={(lp: LabelProps & { index?: number }) => (
                  <BarLabel {...lp} amount={lp.index != null ? (data[lp.index]?.amount ?? null) : null} />
                )}
              >
                {data.map((entry, idx) => (
                  <Cell key={`${entry.name}-${idx}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>
        </div>
      )}

      {/* ── Footer: classes without planned price ── */}
      {withoutPrice.length > 0 && (
        <div className="flex items-center justify-between gap-4 px-5 py-3 border-t border-border-subtle bg-surface-sunken">
          <span className="text-xs text-fg-tertiary">
            {withoutPrice.length} класс{pluralRu(withoutPrice.length)}{" "}
            ({withoutPrice.map((c) => c.material_class_name).join(", ")}) без плановой цены —{" "}
            {withoutPrice.length % 10 === 1 && withoutPrice.length % 100 !== 11
              ? "не учтён в расчёте"
              : "не учтены в расчёте"}
          </span>
          {typeof onConfigurePrice === "function" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onConfigurePrice}
              className="shrink-0 text-xs text-accent-text hover:underline"
            >
              Настроить плановые цены →
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
