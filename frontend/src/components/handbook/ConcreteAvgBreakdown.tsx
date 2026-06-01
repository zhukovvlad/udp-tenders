// allocate() дублирует логику из crud/calculations.py — намеренно, до появления серверного /invoice-breakdown

import { useState } from "react";

import { Surface } from "@/components/ui-domain/Surface";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface ConcreteBaseLine {
  cls: string;
  name: string;
  qty: number;
  sumWithVat: number;
}

export interface ConcreteOtherLine {
  name: string;
  qty: number;
  sumWithVat: number;
}

export interface ConcreteSfData {
  invoiceLabel: string;
  baseLines: ConcreteBaseLine[];
  deliveryWithVat: number;
  additiveWithVat?: number;
  otherLines?: ConcreteOtherLine[];
}

const rubFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const m3Fmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
const pctFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });

const rub = (n: number) => `${rubFmt.format(Math.round(n))} ₽`;
const m3 = (n: number) => `${m3Fmt.format(n)} м³`;
const pct = (n: number) => `${pctFmt.format(n * 100)} %`;

function allocate(data: ConcreteSfData, cls: string) {
  const additive = data.additiveWithVat ?? 0;
  const baseQty = data.baseLines.reduce((s, l) => s + l.qty, 0);
  const line = data.baseLines.find((l) => l.cls === cls) ?? data.baseLines[0];
  const share = baseQty > 0 ? line.qty / baseQty : 0;
  const deliveryAlloc = data.deliveryWithVat * share;
  const additiveAlloc = additive * share;
  const totalWithVat = line.sumWithVat + deliveryAlloc + additiveAlloc;
  const perM3 = line.qty > 0 ? totalWithVat / line.qty : 0;
  return { line, baseQty, share, deliveryAlloc, additiveAlloc, totalWithVat, perM3, additive };
}

export const DEMO_SF: ConcreteSfData = {
  invoiceLabel: "СФ ЦБ-390 · Термобетон",
  baseLines: [
    { cls: "В40", name: "Бетон БСТ В40 П4 F200", qty: 14, sumWithVat: 122640 },
    { cls: "В30", name: "Бетон БСТ В30", qty: 107, sumWithVat: 732360 },
  ],
  deliveryWithVat: 145200,
  additiveWithVat: 0,
  otherLines: [{ name: "Цементное молочко", qty: 1, sumWithVat: 8130 }],
};

interface Props {
  data?: ConcreteSfData;
  initialClass?: string;
}

export function ConcreteAvgBreakdown({ data = DEMO_SF, initialClass }: Props) {
  const [selected, setSelected] = useState(initialClass ?? data.baseLines[0]?.cls ?? "");
  const a = allocate(data, selected);

  const steps: Array<[string, string, string]> = [
    [
      "Суммарный объём бетона (база)",
      data.baseLines.map((l) => m3Fmt.format(l.qty)).join(" + "),
      m3(a.baseQty),
    ],
    ["Доля " + selected + " в объёме", `${m3Fmt.format(a.line.qty)} / ${m3Fmt.format(a.baseQty)}`, pct(a.share)],
    ["Доставка на " + selected, `${rub(data.deliveryWithVat)} × ${pct(a.share)}`, rub(a.deliveryAlloc)],
  ];
  if (a.additive > 0) {
    steps.push(["Присадки на " + selected, `${rub(a.additive)} × ${pct(a.share)}`, rub(a.additiveAlloc)]);
  }
  steps.push(
    ["Стоимость " + selected + " с разнесением", `${rub(a.line.sumWithVat)} + ${rub(a.deliveryAlloc + a.additiveAlloc)}`, rub(a.totalWithVat)],
    ["Делим на объём " + selected, `${rub(a.totalWithVat)} ÷ ${m3(a.line.qty)}`, `${rub(a.perM3)}/м³`],
  );

  return (
    <div className="text-fg">
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <span className="text-sm text-fg-secondary">Считаем класс:</span>
        {data.baseLines.map((l) => {
          const on = l.cls === selected;
          return (
            <button
              key={l.cls}
              type="button"
              onClick={() => setSelected(l.cls)}
              className={
                "rounded-md border px-3.5 py-1 text-sm transition-colors " +
                (on
                  ? "border-accent-border bg-accent-soft text-accent-text"
                  : "border-border-default text-fg-secondary hover:bg-surface-hover")
              }
            >
              {l.cls}
            </button>
          );
        })}
        <span className="ml-auto text-xs text-fg-tertiary">{data.invoiceLabel} · суммы с НДС</span>
      </div>

      <Surface padding="none" className="mb-5">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Строка счёта</TableHead>
              <TableHead className="text-right">Объём</TableHead>
              <TableHead className="text-right">Сумма с НДС</TableHead>
              <TableHead>Роль в расчёте</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.baseLines.map((l) => (
              <TableRow key={l.cls} className={l.cls === selected ? "bg-accent-soft" : ""}>
                <TableCell>{l.name}</TableCell>
                <TableCell className="text-right">{m3(l.qty)}</TableCell>
                <TableCell className="text-right">{rub(l.sumWithVat)}</TableCell>
                <TableCell className="text-fg-secondary">база — основа цены</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>Доставка</TableCell>
              <TableCell className="text-right text-fg-tertiary">база {m3Fmt.format(a.baseQty)}</TableCell>
              <TableCell className="text-right">{rub(data.deliveryWithVat)}</TableCell>
              <TableCell className="text-fg-secondary">разносится по объёму</TableCell>
            </TableRow>
            {(data.otherLines ?? []).map((o) => (
              <TableRow key={o.name} className="opacity-55">
                <TableCell className="line-through">{o.name}</TableCell>
                <TableCell className="text-right">{m3(o.qty)}</TableCell>
                <TableCell className="text-right">{rub(o.sumWithVat)}</TableCell>
                <TableCell className="text-danger-text">прочее — не входит</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Surface>

      <div className="mb-5">
        {steps.map(([label, formula, value], i) => (
          <div key={i} className="flex items-baseline gap-3 border-t border-border-subtle py-2 first:border-t-0">
            <span className="flex-1 text-sm text-fg-secondary">{label}</span>
            <span className="font-mono text-xs text-fg-tertiary">{formula}</span>
            <span className="min-w-[120px] text-right text-sm font-medium">{value}</span>
          </div>
        ))}
      </div>

      <Surface tone="sunken" padding="sm" className="flex items-baseline gap-3">
        <span className="text-sm text-fg-secondary">Средняя цена {selected} по этой СФ</span>
        <span className="ml-auto text-2xl font-medium">{rub(a.perM3)}/м³</span>
      </Surface>
    </div>
  );
}

export default ConcreteAvgBreakdown;
