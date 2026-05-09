import { useMemo, useState } from "react";
import { Search, FolderOpen, Sigma } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { Button } from "@/components/ui-domain/Button";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { KpiCard } from "@/components/ui-domain/KpiCard";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { MoneyCell } from "@/components/ui-domain/MoneyCell";
import { DeviationCell } from "@/components/ui-domain/DeviationCell";
import { InvoiceTable } from "@/components/invoices/InvoiceTable";

import {
  useProjects,
  useMaterialClasses,
  useDashboardSummary,
  useDashboardInvoices,
  useDashboardCalculations,
  useAutoCalculate,
  useCalculate,
} from "@/services/queries";
import { formatNumber, formatMoney, formatDate } from "@/lib/format";
import type { ID } from "@/types/common";

export default function Dashboard() {
  const projectsQ = useProjects();
  const classesQ = useMaterialClasses();

  const [projectId, setProjectId] = useState<ID | null>(null);
  const [classId, setClassId] = useState<ID | null>(null);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [search, setSearch] = useState("");

  const summaryQ = useDashboardSummary(projectId);
  const invoicesQ = useDashboardInvoices(projectId);
  const calcsQ = useDashboardCalculations(projectId);
  const auto = useAutoCalculate();
  const calc = useCalculate();

  const handleProjectChange = async (val: string | null) => {
    const id = val ? Number(val) : null;
    setProjectId(id);
    if (id !== null) {
      try {
        const r = await auto.mutateAsync(id);
        if (r.period_start) setPeriodStart(r.period_start);
        if (r.period_end) setPeriodEnd(r.period_end);
      } catch {
        // ошибки уже обрабатываются глобальным onError мутаций
      }
    }
  };

  const filteredInvoices = useMemo(() => {
    const list = invoicesQ.data ?? [];
    if (!search.trim()) return list;
    const q = search.trim().toLowerCase();
    return list.filter(
      (inv) =>
        inv.number.toLowerCase().includes(q) ||
        (inv.supplier_name ?? "").toLowerCase().includes(q)
    );
  }, [invoicesQ.data, search]);

  return (
    <div className="container-page py-8">
      <PageHeader
        serif
        title="Аналитика"
        subtitle="Отклонения цен по объектам и периодам"
      />

      {/* Контекст: объект + класс материала */}
      <Surface className="mt-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
              Объект *
            </Label>
            <Select
              value={projectId ? String(projectId) : ""}
              onValueChange={handleProjectChange}
            >
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder="Выберите объект" />
              </SelectTrigger>
              <SelectContent>
                {(projectsQ.data ?? []).map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
              Класс материала
            </Label>
            <Select
              value={classId ? String(classId) : ""}
              onValueChange={(v) => setClassId(v ? Number(v) : null)}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Все классы" />
              </SelectTrigger>
              <SelectContent>
                {(classesQ.data ?? []).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
              Период с
            </Label>
            <Input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-[160px]"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
              По
            </Label>
            <Input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="w-[160px]"
            />
          </div>

          <Button
            onClick={() =>
              projectId &&
              periodStart &&
              periodEnd &&
              calc.mutate({
                project_id: projectId,
                material_class_id: classId ?? undefined,
                period_start: periodStart,
                period_end: periodEnd,
              })
            }
            disabled={
              !projectId || !periodStart || !periodEnd || calc.isPending
            }
            loading={calc.isPending}
          >
            Рассчитать
          </Button>
        </div>
      </Surface>

      {/* KPI */}
      {projectId && (
        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {summaryQ.isLoading ? (
            <>
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
            </>
          ) : summaryQ.data ? (
            <>
              <KpiCard
                label="Документов"
                value={formatNumber(summaryQ.data.doc_count)}
              />
              <KpiCard
                label="Счетов-фактур"
                value={formatNumber(summaryQ.data.invoice_count)}
              />
              <KpiCard
                label="Объём, м³"
                value={formatNumber(summaryQ.data.total_qty)}
              />
              <KpiCard
                label="Сумма"
                value={formatMoney(summaryQ.data.total_amount)}
              />
            </>
          ) : null}
        </div>
      )}

      {/* Расчёты отклонений */}
      {projectId && (calcsQ.data ?? []).length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 font-serif text-xl font-medium text-fg">
            Отклонения от эталона
          </h2>
          <Surface padding="none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Класс</TableHead>
                  <TableHead>Период</TableHead>
                  <TableHead className="text-right">Ср. цена</TableHead>
                  <TableHead className="text-right">Эталон</TableHead>
                  <TableHead className="text-right">Откл. %</TableHead>
                  <TableHead className="text-right">Откл. ₽</TableHead>
                  <TableHead className="text-right">Объём</TableHead>
                  <TableHead className="text-right">СФ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(calcsQ.data ?? []).map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">
                      {row.material_class_name}
                    </TableCell>
                    <TableCell className="text-fg-secondary">
                      {formatDate(row.period_start)} — {formatDate(row.period_end)}
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyCell value={row.avg_price} />
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyCell value={row.reference_price} />
                    </TableCell>
                    <TableCell className="text-right">
                      <DeviationCell value={row.deviation_pct} />
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyCell value={row.deviation_amount} />
                    </TableCell>
                    <TableCell className="text-right text-fg-secondary tabular-nums">
                      {formatNumber(row.total_qty)}
                    </TableCell>
                    <TableCell className="text-right text-fg-secondary tabular-nums">
                      {row.invoice_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Surface>
        </section>
      )}

      {/* Список СФ */}
      {projectId && (
        <section className="mt-8">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-serif text-xl font-medium text-fg">
              Счета-фактуры
              {invoicesQ.data && (
                <span className="ml-2 text-sm font-normal text-fg-tertiary">
                  · {invoicesQ.data.length}
                </span>
              )}
            </h2>
            <div className="relative w-[280px]">
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-tertiary"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по номеру или поставщику"
                className="w-full rounded-md border border-border-subtle bg-surface py-1.5 pl-9 pr-3 text-sm text-fg placeholder:text-fg-tertiary focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>
          </div>

          {invoicesQ.isLoading ? (
            <Surface padding="none">
              <div className="space-y-1 p-2">
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
              </div>
            </Surface>
          ) : (filteredInvoices.length === 0) ? (
            <EmptyState
              title={search ? "Ничего не найдено" : "Нет загруженных документов"}
              description={
                search
                  ? "Попробуйте изменить запрос."
                  : "Начните с загрузки счетов-фактур."
              }
              action={
                !search ? (
                  <a href="/upload">
                    <Button>Загрузить документ</Button>
                  </a>
                ) : undefined
              }
            />
          ) : (
            <Surface padding="none">
              <InvoiceTable invoices={filteredInvoices} />
            </Surface>
          )}
        </section>
      )}

      {/* Empty state: объект не выбран */}
      {!projectId && !projectsQ.isLoading && (
        <div className="mt-8">
          <EmptyState
            icon={<FolderOpen size={20} />}
            title="Выберите объект"
            description="Аналитика отображается по выбранному объекту. Выберите проект из списка выше или создайте новый."
            action={
              <a href="/projects">
                <Button variant="secondary">К списку объектов</Button>
              </a>
            }
          />
        </div>
      )}

      {/* Empty state: нет данных по проекту */}
      {projectId &&
        summaryQ.data &&
        summaryQ.data.invoice_count === 0 &&
        (invoicesQ.data ?? []).length === 0 && (
          <div className="mt-8">
            <EmptyState
              icon={<Sigma size={20} />}
              title="Нет данных по этому объекту"
              description="Загрузите счета-фактуры, чтобы увидеть аналитику."
              action={
                <a href="/upload">
                  <Button>Загрузить документ</Button>
                </a>
              }
            />
          </div>
        )}
    </div>
  );
}
