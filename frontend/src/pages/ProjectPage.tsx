import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, Plus } from "lucide-react";

import { Breadcrumbs } from "@/components/ui-domain/Breadcrumbs";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { Button } from "@/components/ui-domain/Button";
import { KpiCard } from "@/components/ui-domain/KpiCard";
import { InvoiceTable } from "@/components/invoices/InvoiceTable";
import { UploadSheet } from "@/components/projects/UploadSheet";
import { DeviationChart } from "@/components/projects/DeviationChart";

import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

import {
  useProjects,
  useDashboardSummary,
  useDashboardInvoices,
  useDashboardCalculations,
  useCalculate,
  useAutoCalculate,
  useReferencePrices,
  useCreateReferencePrice,
  useMaterialClasses,
} from "@/services/queries";

import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import type { ID } from "@/types/common";
import type { DashboardCalculation } from "@/types/dashboard";

// ─────────────────────────────────────────────
// Helper: total deviation across all calculations
// ─────────────────────────────────────────────
function totalDeviationAmount(
  calculations: DashboardCalculation[]
): number {
  return calculations.reduce((sum, c) => sum + (c.deviation_amount ?? 0), 0);
}

// ─────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────
export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const parsed = id ? Number(id) : NaN;
  const projectId: ID | null = Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  // ── upload sheet ──
  const [uploadOpen, setUploadOpen] = useState(false);

  // ── calculation period controls ──
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");

  // ── active tab ──
  const [activeTab, setActiveTab] = useState("overview");

  // ── reference price dialog ──
  const [priceDialogOpen, setPriceDialogOpen] = useState(false);
  const [rpClassId, setRpClassId] = useState<string>("");
  const [rpPrice, setRpPrice] = useState("");
  const [rpStart, setRpStart] = useState("");
  const [rpEnd, setRpEnd] = useState("");
  const [rpSource, setRpSource] = useState("");

  // ── queries ──
  const projectsQ = useProjects();
  const project = projectsQ.data?.find((p) => p.id === projectId) ?? null;

  const summaryQ = useDashboardSummary(projectId);
  const invoicesQ = useDashboardInvoices(projectId);
  const calculationsQ = useDashboardCalculations(projectId);
  const hasValidProjectId = projectId !== null;
  const referencePricesQ = useReferencePrices(
    hasValidProjectId ? projectId : undefined,
    { enabled: hasValidProjectId },
  );
  const materialClassesQ = useMaterialClasses();

  // ── mutations ──
  const calculateMut = useCalculate();
  const autoCalculateMut = useAutoCalculate();
  const createRefPrice = useCreateReferencePrice();

  // ── derived ──
  const calculations = calculationsQ.data ?? [];
  const invoices = invoicesQ.data ?? [];
  const referencePrices = referencePricesQ.data ?? [];
  const materialClasses = materialClassesQ.data ?? [];

  const hasCalculations = calculations.length > 0;
  const totalDev = totalDeviationAmount(calculations);

  // Aggregate suppliers from invoices
  const supplierMap = new Map<string, { displayName: string; count: number }>();
  for (const inv of invoices) {
    const key = inv.supplier_inn
      ? `inn:${inv.supplier_inn}`
      : inv.supplier_name
        ? `name:${inv.supplier_name}`
        : "unknown";
    const displayName = inv.supplier_name ?? inv.supplier_inn ?? "(без названия)";
    const existing = supplierMap.get(key);
    supplierMap.set(key, { displayName, count: (existing?.count ?? 0) + 1 });
  }
  const suppliers = Array.from(supplierMap.entries()).map(([key, { displayName, count }]) => ({
    key,
    name: displayName,
    count,
  }));

  // ── loading / not found ──
  if (projectsQ.isLoading) {
    return (
      <div className="container-page py-8 space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-[120px]" />
      </div>
    );
  }

  if (!project || projectId === null) {
    return (
      <div className="container-page py-8">
        <EmptyState
          title="Объект не найден"
          action={
            <Link to="/projects">
              <Button variant="secondary" leftIcon={<ArrowLeft size={14} />}>
                К списку объектов
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  // ── handlers ──
  function handleCalculate() {
    if (!projectId || !periodStart || !periodEnd) return;
    calculateMut.mutate({
      project_id: projectId,
      period_start: periodStart,
      period_end: periodEnd,
    });
  }

  function handleAutoCalculate() {
    if (!projectId) return;
    autoCalculateMut.mutate(projectId);
  }

  function handleAddReferencePrice() {
    if (!projectId || !rpClassId || !rpPrice || !rpStart || !rpEnd) return;
    createRefPrice.mutate(
      {
        project_id: projectId,
        material_class_id: Number(rpClassId),
        price: Number(rpPrice),
        period_start: rpStart,
        period_end: rpEnd,
        source: rpSource || null,
      },
      {
        onSuccess: () => {
          setPriceDialogOpen(false);
          setRpClassId("");
          setRpPrice("");
          setRpStart("");
          setRpEnd("");
          setRpSource("");
        },
      }
    );
  }

  return (
    <div className="container-page py-8">
      {/* Breadcrumbs */}
      <Breadcrumbs
        items={[
          { label: "Объекты", to: "/projects" },
          { label: project.name },
        ]}
      />

      {/* Header */}
      <div className="mt-3">
        <PageHeader
          serif
          title={project.name}
          subtitle={
            project.contract_number
              ? `Договор № ${project.contract_number} · создан ${formatDate(project.created_at)}`
              : `Создан ${formatDate(project.created_at)}`
          }
          actions={
            <>
              <Button variant="secondary" leftIcon={<Download size={14} />}>
                Экспорт
              </Button>
              <Button
                leftIcon={<Plus size={14} />}
                onClick={() => setUploadOpen(true)}
              >
                + Добавить счёт
              </Button>
            </>
          }
        />
      </div>

      {/* Upload sheet */}
      <UploadSheet
        projectId={projectId}
        open={uploadOpen}
        onOpenChange={setUploadOpen}
      />

      {/* Tabs */}
      <div className="mt-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} data-testid="project-page-tabs">
          <TabsList variant="line" data-testid="project-page-tabs-list">
            <TabsTrigger value="overview" data-testid="project-tab-overview">Обзор</TabsTrigger>
            <TabsTrigger value="invoices" data-testid="project-tab-invoices">
              Счета{invoices.length > 0 ? ` · ${invoices.length}` : ""}
            </TabsTrigger>
            <TabsTrigger value="prices" data-testid="project-tab-prices">Плановые цены</TabsTrigger>
            <TabsTrigger value="suppliers" data-testid="project-tab-suppliers">
              Поставщики{suppliers.length > 0 ? ` · ${suppliers.length}` : ""}
            </TabsTrigger>
          </TabsList>

          {/* ────────── TAB: Обзор ────────── */}
          <TabsContent value="overview" className="mt-6 space-y-6">
            {/* Verdict banner */}
            {hasCalculations && (() => {
              // Show the full covered range (min start → max end) since totalDev spans all periods
              const rangeStart = calculations.reduce((min, c) =>
                c.period_start < min ? c.period_start : min, calculations[0].period_start
              );
              const rangeEnd = calculations.reduce((max, c) =>
                c.period_end > max ? c.period_end : max, calculations[0].period_end
              );
              const calcPeriod = `${formatDate(rangeStart)} — ${formatDate(rangeEnd)}`;
              return (
                <div
                  className={
                    totalDev > 0
                      ? "rounded-lg bg-danger-soft border border-danger-border px-4 py-3 text-sm font-medium text-danger-text flex items-center justify-between gap-4"
                      : "rounded-lg bg-accent-soft border border-accent-border px-4 py-3 text-sm font-medium text-accent-text flex items-center justify-between gap-4"
                  }
                >
                  <span>
                    {totalDev > 0
                      ? `Переплата: +${formatMoney(totalDev)}`
                      : `Экономия: ${formatMoney(Math.abs(totalDev))}`}
                  </span>
                  {calcPeriod && (
                    <span className="text-xs font-normal opacity-60">{calcPeriod}</span>
                  )}
                </div>
              );
            })()}

            {/* KPI row */}
            {summaryQ.data && (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  label="Оборот"
                  value={formatMoney(summaryQ.data.total_amount)}
                />
                <KpiCard
                  label="Объём м³"
                  value={formatNumber(summaryQ.data.total_qty)}
                />
                <KpiCard
                  label="Счетов"
                  value={formatNumber(summaryQ.data.invoice_count)}
                />
                <KpiCard
                  label="Документов"
                  value={formatNumber(summaryQ.data.doc_count)}
                />
              </div>
            )}

            {/* Calculation controls */}
            <div className="rounded-lg border border-border-subtle bg-surface p-4 space-y-3">
              {hasCalculations && (() => {
                const latestCalc = calculations.reduce((a, b) =>
                  new Date(a.period_end) >= new Date(b.period_end) ? a : b
                );
                return (
                  <div className="text-xs text-fg-tertiary">
                    Последний расчёт: {formatDate(latestCalc.period_start)} — {formatDate(latestCalc.period_end)}
                  </div>
                );
              })()}
              <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-fg-secondary">
                  Период с
                </label>
                <Input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="w-40"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-fg-secondary">
                  Период по
                </label>
                <Input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="w-40"
                />
              </div>
              <Button
                onClick={handleCalculate}
                loading={calculateMut.isPending}
                disabled={!periodStart || !periodEnd}
              >
                Рассчитать
              </Button>
              <Button
                variant="secondary"
                onClick={handleAutoCalculate}
                loading={autoCalculateMut.isPending}
              >
                Авто
              </Button>
              </div>
            </div>

            {/* Deviation chart */}
            {hasCalculations && (
              <DeviationChart
                calculations={calculations}
                onConfigurePrice={() => setActiveTab("prices")}
              />
            )}

            {/* Calculations table */}
            {hasCalculations && (
              <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle text-left text-xs text-fg-tertiary">
                      <th className="px-4 py-2 font-medium">Класс</th>
                      <th className="px-4 py-2 font-medium">Период</th>
                      <th className="px-4 py-2 font-medium text-right">Ср.цена</th>
                      <th className="px-4 py-2 font-medium text-right">Плановая цена</th>
                      <th className="px-4 py-2 font-medium text-right">Откл.%</th>
                      <th className="px-4 py-2 font-medium text-right">Откл.₽</th>
                      <th className="px-4 py-2 font-medium text-right">Объём</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calculations.map((c) => (
                      <tr
                        key={`${c.material_class_name ?? ""}-${c.period_start}-${c.period_end}`}
                        className="border-b border-border-subtle last:border-0 hover:bg-surface-hover"
                      >
                        <td className="px-4 py-2 text-fg">
                          {c.material_class_name}
                        </td>
                        <td className="px-4 py-2 text-fg-secondary whitespace-nowrap">
                          {formatDate(c.period_start)} — {formatDate(c.period_end)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-fg">
                          {formatMoney(c.avg_price)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-fg-secondary">
                          {c.reference_price !== null
                            ? formatMoney(c.reference_price)
                            : "—"}
                        </td>
                        <td
                          className={
                            "px-4 py-2 text-right font-mono " +
                            (c.deviation_pct == null
                              ? "text-fg-secondary"
                              : c.deviation_pct > 0
                              ? "text-danger-text"
                              : "text-accent-text")
                          }
                        >
                          {formatPercent(c.deviation_pct, true)}
                        </td>
                        <td
                          className={
                            "px-4 py-2 text-right font-mono " +
                            (c.deviation_amount == null
                              ? "text-fg-secondary"
                              : c.deviation_amount > 0
                              ? "text-danger-text"
                              : "text-accent-text")
                          }
                        >
                          {c.deviation_amount !== null
                            ? formatMoney(c.deviation_amount)
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-fg-secondary">
                          {formatNumber(c.total_qty)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </TabsContent>

          {/* ────────── TAB: Счета ────────── */}
          <TabsContent value="invoices" className="mt-6">
            {invoicesQ.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
              </div>
            ) : invoices.length === 0 ? (
              <EmptyState
                title="Нет счетов-фактур"
                description="Загрузите документы, чтобы они появились здесь."
                action={
                  <Button onClick={() => setUploadOpen(true)}>Загрузить</Button>
                }
              />
            ) : (
              <div className="overflow-hidden rounded-lg border border-border-subtle bg-surface">
                <InvoiceTable invoices={invoices} />
              </div>
            )}
          </TabsContent>

          {/* ────────── TAB: Плановые цены ────────── */}
          <TabsContent value="prices" className="mt-6 space-y-4">
            <div className="flex justify-end">
              <Button
                leftIcon={<Plus size={14} />}
                onClick={() => setPriceDialogOpen(true)}
              >
                Добавить
              </Button>
            </div>

            {referencePricesQ.isLoading ? (
              <Skeleton className="h-32" />
            ) : referencePrices.length === 0 ? (
              <EmptyState
                title="Нет плановых цен"
                description="Добавьте плановые цены для расчёта отклонений."
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle text-left text-xs text-fg-tertiary">
                      <th className="px-4 py-2 font-medium">Класс</th>
                      <th className="px-4 py-2 font-medium text-right">Цена</th>
                      <th className="px-4 py-2 font-medium">Период</th>
                      <th className="px-4 py-2 font-medium">Источник</th>
                    </tr>
                  </thead>
                  <tbody>
                    {referencePrices.map((rp) => (
                      <tr
                        key={rp.id}
                        className="border-b border-border-subtle last:border-0 hover:bg-surface-hover"
                      >
                        <td className="px-4 py-2 text-fg">
                          {rp.material_class_name ?? `#${rp.material_class_id}`}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-fg">
                          {formatMoney(rp.price)}
                        </td>
                        <td className="px-4 py-2 text-fg-secondary whitespace-nowrap">
                          {formatDate(rp.period_start)} — {formatDate(rp.period_end)}
                        </td>
                        <td className="px-4 py-2 text-fg-secondary">
                          {rp.source ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Add reference price dialog */}
            <Dialog open={priceDialogOpen} onOpenChange={setPriceDialogOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Добавить плановую цену</DialogTitle>
                </DialogHeader>

                <div className="space-y-3 py-2">
                  {/* Material class selector */}
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-fg-secondary">
                      Класс материала
                    </label>
                    <Select value={rpClassId} onValueChange={(v) => setRpClassId(v ?? "")}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Выберите класс…" />
                      </SelectTrigger>
                      <SelectContent>
                        {materialClasses.map((mc) => (
                          <SelectItem key={mc.id} value={String(mc.id)}>
                            {mc.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Price */}
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-fg-secondary">
                      Цена (₽)
                    </label>
                    <Input
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="0.00"
                      value={rpPrice}
                      onChange={(e) => setRpPrice(e.target.value)}
                    />
                  </div>

                  {/* Period */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-fg-secondary">
                        Период с
                      </label>
                      <Input
                        type="date"
                        value={rpStart}
                        onChange={(e) => setRpStart(e.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-fg-secondary">
                        Период по
                      </label>
                      <Input
                        type="date"
                        value={rpEnd}
                        onChange={(e) => setRpEnd(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Source */}
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-fg-secondary">
                      Источник
                    </label>
                    <Input
                      placeholder="Необязательно"
                      value={rpSource}
                      onChange={(e) => setRpSource(e.target.value)}
                    />
                  </div>
                </div>

                <DialogFooter>
                  <Button
                    onClick={handleAddReferencePrice}
                    loading={createRefPrice.isPending}
                    disabled={
                      !rpClassId || !rpPrice || !rpStart || !rpEnd
                    }
                  >
                    Сохранить
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </TabsContent>

          {/* ────────── TAB: Поставщики ────────── */}
          <TabsContent value="suppliers" className="mt-6">
            {invoicesQ.isLoading ? (
              <Skeleton className="h-32" />
            ) : suppliers.length === 0 ? (
              <EmptyState
                title="Нет поставщиков"
                description="Загрузите счета-фактуры, чтобы увидеть поставщиков."
                action={
                  <Button onClick={() => setUploadOpen(true)}>Загрузить</Button>
                }
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle text-left text-xs text-fg-tertiary">
                      <th className="px-4 py-2 font-medium">Поставщик</th>
                      <th className="px-4 py-2 font-medium text-right">Счетов</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.map((s) => (
                      <tr
                        key={s.key}
                        className="border-b border-border-subtle last:border-0 hover:bg-surface-hover"
                      >
                        <td className="px-4 py-2 text-fg">{s.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-fg-secondary">
                          {s.count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
