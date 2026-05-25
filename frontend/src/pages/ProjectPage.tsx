import { toast } from "sonner";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, Loader2, Plus, Trash2, Pencil } from "lucide-react";

import { Breadcrumbs } from "@/components/ui-domain/Breadcrumbs";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { Button } from "@/components/ui-domain/Button";
import { KpiCard } from "@/components/ui-domain/KpiCard";
import { InvoiceTable } from "@/components/invoices/InvoiceTable";
import { UploadSheet } from "@/components/projects/UploadSheet";
import { DeviationChart } from "@/components/projects/DeviationChart";
import { MonthlyTab } from "@/components/projects/MonthlyTab";

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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";

import {
  useProjects,
  useDashboardSummary,
  useDashboardInvoices,
  useDashboardCalculations,
  useReferencePrices,
  useCreateReferencePrice,
  useUpdateReferencePrice,
  useDeleteReferencePrice,
  useMaterialClasses,
  useProjectSuppliers,
  useSupplierExclusions,
  useToggleSupplierExclusion,
} from "@/services/queries";
import { reportsApi } from "@/services/api/reports";
import { useDebounce } from "@/lib/useDebounce";

import { formatDate, formatMoney, formatNumber, formatPercent, pluralRu } from "@/lib/format";
import { MONTH_NAMES_RU } from "@/lib/constants";
import type { ID } from "@/types/common";
import type { ReferencePrice } from "@/types/referencePrice";

// ─────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────
export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const parsed = id ? Number(id) : NaN;
  const projectId: ID | null = Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  // ── upload sheet ──
  const [uploadOpen, setUploadOpen] = useState(false);

  // ── export ──
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!projectId || isExporting) return;
    setIsExporting(true);
    try {
      const blob = await reportsApi.excelBlob({
        project_id: projectId,
        period_start: periodStart || undefined,
        period_end: periodEnd || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeName = String(project?.name ?? projectId)
        .replace(/[\\/:*?"<>|\r\n]/g, "-")
        .trim()
        .replace(/^[ .-]+|[ .-]+$/g, "");
      const periodSuffix = periodStart || periodEnd ? `_${periodStart || ""}–${periodEnd || ""}` : "";
      a.download = `отчёт-${safeName || projectId}${periodSuffix}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL?.(url), 0);
    } catch (err) {
      // axios blob responses return error body as Blob — parse it to get backend detail
      let message = "Не удалось сформировать отчёт";
      try {
        const blob = (err as { response?: { data?: unknown } })?.response?.data;
        if (blob instanceof Blob) {
          const json = JSON.parse(await blob.text()) as { detail?: unknown };
          if (typeof json.detail === "string") message = json.detail;
        }
      } catch {
        // ignore parse errors, keep generic message
      }
      toast.error(message);
    } finally {
      setIsExporting(false);
    }
  };

  // ── calculation period filters ──
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const debouncedPeriodStart = useDebounce(periodStart, 400);
  const debouncedPeriodEnd = useDebounce(periodEnd, 400);

  // ── active tab ──
  const [activeTab, setActiveTab] = useState("overview");

  // ── invoice month filter (set when navigating from «По месяцам» tab) ──
  const [invoiceMonthFilter, setInvoiceMonthFilter] = useState<{ year: number; month: number } | null>(null);

  // ── reference price dialog ──
  const [priceDialogOpen, setPriceDialogOpen] = useState(false);
  const [rpClassId, setRpClassId] = useState<string>("");
  const [rpPrice, setRpPrice] = useState("");
  const [rpStart, setRpStart] = useState("");
  const [rpEnd, setRpEnd] = useState("");
  const [rpSource, setRpSource] = useState("");

  // ── edit reference price dialog ──
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editRpId, setEditRpId] = useState<number | null>(null);
  const [editPrice, setEditPrice] = useState("");
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");
  const [editSource, setEditSource] = useState("");

  // ── delete reference price dialog ──
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteRpId, setDeleteRpId] = useState<number | null>(null);

  // ── exclusion inline form ──
  const [exclusionPopover, setExclusionPopover] = useState<{
    supplierId: number;
    reason: string;
  } | null>(null);

  // ── queries ──
  const projectsQ = useProjects();
  const project = projectsQ.data?.find((p) => p.id === projectId) ?? null;

  const summaryQ = useDashboardSummary(projectId);
  const invoicesQ = useDashboardInvoices(projectId);
  const calculationsQ = useDashboardCalculations(
    projectId,
    debouncedPeriodStart || undefined,
    debouncedPeriodEnd || undefined,
  );
  const hasValidProjectId = projectId !== null;
  const referencePricesQ = useReferencePrices(
    hasValidProjectId ? projectId : undefined,
    { enabled: hasValidProjectId },
  );
  const materialClassesQ = useMaterialClasses();

  // ── project suppliers ──
  const projectSuppliersQ = useProjectSuppliers(projectId);
  const supplierExclusionsQ = useSupplierExclusions(projectId);
  const toggleExclusion = useToggleSupplierExclusion(projectId);

  // ── mutations ──
  const createRefPrice = useCreateReferencePrice();
  const updateRefPrice = useUpdateReferencePrice();
  const deleteRefPrice = useDeleteReferencePrice();

  // ── derived ──
  const calculations = useMemo(() => calculationsQ.data ?? [], [calculationsQ.data]);
  const invoices = useMemo(() => invoicesQ.data ?? [], [invoicesQ.data]);
  const referencePrices = referencePricesQ.data ?? [];
  const materialClasses = materialClassesQ.data ?? [];

  const hasCalculations = calculations.length > 0;

  // Effective period: user's filter OR auto-detected from returned data (cosmetic display only,
  // not sent to the API — API auto-detects when periodStart/periodEnd are empty).
  const dataStart = useMemo(
    () => calculations.length > 0
      ? calculations.reduce((m, c) => (c.period_start < m ? c.period_start : m), calculations[0].period_start)
      : "",
    [calculations],
  );
  const dataEnd = useMemo(
    () => calculations.length > 0
      ? calculations.reduce((m, c) => (c.period_end > m ? c.period_end : m), calculations[0].period_end)
      : "",
    [calculations],
  );
  const displayStart = periodStart || dataStart;
  const displayEnd   = periodEnd   || dataEnd;

  const filteredInvoices = useMemo(() => {
    if (!invoiceMonthFilter) return invoices;
    return invoices.filter((inv) => {
      const [yearPart, monthPart] = (inv.date ?? "").split("-");
      return (
        Number(yearPart) === invoiceMonthFilter.year &&
        Number(monthPart) === invoiceMonthFilter.month
      );
    });
  }, [invoices, invoiceMonthFilter]);

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

  function openEditDialog(rp: ReferencePrice) {
    setEditRpId(rp.id);
    setEditPrice(String(rp.price));
    setEditStart(rp.period_start);
    setEditEnd(rp.period_end);
    setEditSource(rp.source ?? "");
    setEditDialogOpen(true);
  }

  function handleEditReferencePrice() {
    const parsedPrice = parseFloat(editPrice);
    if (!editRpId || !Number.isFinite(parsedPrice) || parsedPrice < 0 || !editStart || !editEnd) return;
    updateRefPrice.mutate(
      {
        id: editRpId,
        input: {
          price: parsedPrice,
          period_start: editStart,
          period_end: editEnd,
          source: editSource || null,
        },
      },
      {
        onSuccess: () => {
          setEditDialogOpen(false);
          setEditRpId(null);
        },
      }
    );
  }

  function openDeleteDialog(id: number) {
    setDeleteRpId(id);
    setDeleteDialogOpen(true);
  }

  function handleDeleteReferencePrice() {
    if (!deleteRpId) return;
    deleteRefPrice.mutate(deleteRpId, {
      onSuccess: () => {
        setDeleteDialogOpen(false);
        setDeleteRpId(null);
      },
      onError: () => {
        setDeleteDialogOpen(false);
        setDeleteRpId(null);
      },
    });
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
              <Button
                variant="secondary"
                leftIcon={<Download size={14} />}
                onClick={handleExport}
                disabled={isExporting}
              >
                {isExporting ? "Формирую..." : "Экспорт"}
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
              Поставщики{(projectSuppliersQ.data?.length ?? 0) > 0 ? ` · ${projectSuppliersQ.data!.length}` : ""}
            </TabsTrigger>
            <TabsTrigger value="monthly" data-testid="project-tab-monthly">По месяцам</TabsTrigger>
          </TabsList>

          {/* ────────── TAB: Обзор ────────── */}
          <TabsContent value="overview" className="mt-6 space-y-6">
            {/* KPI row */}
            {summaryQ.data && (() => {
              const { first_invoice_date, last_invoice_date, full_deviation_amount } = summaryQ.data;

              const devLabel =
                full_deviation_amount != null
                  ? full_deviation_amount > 0
                    ? `+${formatMoney(full_deviation_amount)}`
                    : formatMoney(Math.abs(full_deviation_amount))
                  : "—";
              const devKpiLabel =
                full_deviation_amount != null
                  ? full_deviation_amount > 0
                    ? "Переплата за весь период"
                    : "Экономия за весь период"
                  : "Отклонение (весь период)";
              const devClass =
                full_deviation_amount != null
                  ? full_deviation_amount > 0
                    ? "bg-danger-soft border-danger-border"
                    : "bg-accent-soft border-accent-border"
                  : "";
              const devValueClass =
                full_deviation_amount != null
                  ? full_deviation_amount > 0
                    ? "text-danger-text"
                    : "text-accent-text"
                  : "";

              return (
                <>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <KpiCard
                      label="Оборот, ₽ с НДС"
                      value={formatMoney(summaryQ.data.total_amount)}
                      breakdown={[
                        { label: "Материалы", value: formatMoney(summaryQ.data.material_amount) },
                        ...(summaryQ.data.delivery_amount > 0 ? [{ label: "Доставка", value: formatMoney(summaryQ.data.delivery_amount) }] : []),
                        ...(summaryQ.data.other_amount > 0 ? [{ label: "Прочее", value: formatMoney(summaryQ.data.other_amount) }] : []),
                      ]}
                    />
                    <KpiCard
                      label="Объём м³"
                      value={formatNumber(summaryQ.data.total_qty)}
                    />
                    <KpiCard
                      label="Счетов"
                      value={formatNumber(summaryQ.data.invoice_count)}
                      suffix={`· ${formatNumber(summaryQ.data.doc_count)} докум.`}
                    />
                    <KpiCard
                      label={devKpiLabel}
                      value={devLabel}
                      className={devClass}
                      valueClassName={devValueClass}
                    />
                  </div>
                  <p className="text-xs text-fg-tertiary -mt-2 px-1">
                    Первый счёт{" "}
                    <span className="text-fg-secondary font-medium">
                      {first_invoice_date ? formatDate(first_invoice_date) : "—"}
                    </span>
                    {" · "}
                    Последний счёт{" "}
                    <span className="text-fg-secondary font-medium">
                      {last_invoice_date ? formatDate(last_invoice_date) : "—"}
                    </span>
                    {(projectSuppliersQ.data?.length ?? 0) > 0 && (
                      <>
                        {" · "}
                        <span className="text-fg-secondary font-medium">{formatNumber(projectSuppliersQ.data!.length)}</span>
                        {` поставщик${pluralRu(projectSuppliersQ.data!.length)}`}
                      </>
                    )}
                  </p>
                </>
              );
            })()}

            {/* Exclusion banner */}
            {(supplierExclusionsQ.data?.size ?? 0) > 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface px-4 py-2 text-sm text-fg-secondary -mt-2">
                <span>
                  {`Исключено ${supplierExclusionsQ.data!.size} поставщик${pluralRu(supplierExclusionsQ.data!.size)} из расчётов`}
                </span>
                <button
                  className="ml-auto text-xs underline hover:text-fg"
                  onClick={() => setActiveTab("suppliers")}
                >
                  Управление
                </button>
              </div>
            )}

            {/* Deviation chart (includes period filter in header) */}
            {summaryQ.data && (
              <DeviationChart
                calculations={calculations}
                periodFilterActive={true}
                onConfigurePrice={() => setActiveTab("prices")}
                periodStart={periodStart}
                periodEnd={periodEnd}
                dataStart={dataStart}
                dataEnd={dataEnd}
                displayStart={displayStart}
                displayEnd={displayEnd}
                onPeriodStartChange={setPeriodStart}
                onPeriodEndChange={setPeriodEnd}
                onPeriodReset={() => { setPeriodStart(""); setPeriodEnd(""); }}
              />
            )}

            {/* Calculations table */}
            {hasCalculations && (
              <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
                <Table className="min-w-max">
                  <TableHeader>
                    <TableRow className="text-xs text-fg-tertiary hover:bg-transparent">
                      <TableHead className="font-medium">Класс</TableHead>
                      <TableHead className="font-medium">Период</TableHead>
                      <TableHead className="font-medium text-right">
                        <div>Ср.цена</div>
                        <div className="text-[10px] font-normal text-fg-tertiary">с НДС</div>
                      </TableHead>
                      <TableHead className="font-medium text-right">
                        <div>Плановая цена</div>
                        <div className="text-[10px] font-normal text-fg-tertiary">с НДС</div>
                      </TableHead>
                      <TableHead className="font-medium text-right">Откл.%</TableHead>
                      <TableHead className="font-medium text-right">Откл.₽</TableHead>
                      <TableHead className="font-medium text-right">Объём</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...calculations]
                      .sort((a, b) => {
                        const pCmp = a.period_start.localeCompare(b.period_start);
                        if (pCmp !== 0) return pCmp;
                        // Sort by numeric concrete strength (B7.5 < B10 < B15 < B30 ...)
                        const num = (name: string | null | undefined) => {
                          const m = (name ?? "").match(/[\d.]+/);
                          return m ? parseFloat(m[0]) : 0;
                        };
                        return num(a.material_class_name) - num(b.material_class_name);
                      })
                      .map((c) => (
                      <TableRow
                        key={`${c.material_class_name ?? ""}-${c.period_start}-${c.period_end}`}
                      >
                        <TableCell className="text-fg">
                          {c.material_class_name}
                        </TableCell>
                        <TableCell className="text-fg-secondary whitespace-nowrap font-mono text-sm">
                          {formatDate(c.period_start)} — {formatDate(c.period_end)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-fg">
                          {formatMoney(c.avg_price)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-fg-secondary">
                          {c.reference_price !== null
                            ? formatMoney(c.reference_price)
                            : "—"}
                        </TableCell>
                        <TableCell
                          className={
                            "text-right font-mono " +
                            (c.deviation_pct == null
                              ? "text-fg-secondary"
                              : c.deviation_pct > 0
                              ? "text-danger-text"
                              : "text-accent-text")
                          }
                        >
                          {formatPercent(c.deviation_pct, true)}
                        </TableCell>
                        <TableCell
                          className={
                            "text-right font-mono " +
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
                        </TableCell>
                        <TableCell className="text-right font-mono text-fg-secondary">
                          {formatNumber(c.total_qty)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
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
              <>
                {invoiceMonthFilter && (
                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-xs text-fg-secondary">
                      Фильтр: {MONTH_NAMES_RU[invoiceMonthFilter.month - 1]} {invoiceMonthFilter.year}
                    </span>
                    <button
                      className="text-xs text-fg-tertiary hover:text-fg underline"
                      onClick={() => setInvoiceMonthFilter(null)}
                    >
                      Сбросить
                    </button>
                  </div>
                )}
                <div className="overflow-hidden rounded-lg border border-border-subtle bg-surface">
                  <InvoiceTable
                    invoices={filteredInvoices}
                  />
                </div>
              </>
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
                      <th className="px-4 py-2 font-medium text-right">
                        <div>Цена</div>
                        <div className="text-[10px] font-normal text-fg-tertiary">с НДС</div>
                      </th>
                      <th className="px-4 py-2 font-medium">Период</th>
                      <th className="px-4 py-2 font-medium">Источник</th>
                      <th className="px-4 py-2 w-20"></th>
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
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-1 justify-end">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditDialog(rp)}
                              aria-label="Редактировать"
                              data-testid={`rp-edit-${rp.id}`}
                            >
                              <Pencil size={14} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openDeleteDialog(rp.id)}
                              aria-label="Удалить"
                              data-testid={`rp-delete-${rp.id}`}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </div>
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

            {/* Edit reference price dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Редактировать плановую цену</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-fg-secondary">Цена (₽)</label>
                    <Input
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="0.00"
                      value={editPrice}
                      onChange={(e) => setEditPrice(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-fg-secondary">Период с</label>
                      <Input
                        type="date"
                        value={editStart}
                        onChange={(e) => setEditStart(e.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-fg-secondary">Период по</label>
                      <Input
                        type="date"
                        value={editEnd}
                        onChange={(e) => setEditEnd(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-fg-secondary">Источник</label>
                    <Input
                      placeholder="Необязательно"
                      value={editSource}
                      onChange={(e) => setEditSource(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    onClick={handleEditReferencePrice}
                    loading={updateRefPrice.isPending}
                    disabled={!Number.isFinite(parseFloat(editPrice)) || parseFloat(editPrice) < 0 || !editStart || !editEnd}
                  >
                    Сохранить
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            {/* Delete confirmation dialog */}
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Удалить плановую цену?</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-fg-secondary py-2">
                  Это действие нельзя отменить.
                </p>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setDeleteDialogOpen(false)}>
                    Отмена
                  </Button>
                  <Button
                    data-testid="rp-delete-confirm"
                    onClick={handleDeleteReferencePrice}
                    loading={deleteRefPrice.isPending}
                  >
                    Удалить
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </TabsContent>
          {/* ────────── TAB: По месяцам ────────── */}
          <TabsContent value="monthly">
            <MonthlyTab
              projectId={projectId}
              projectName={project.name}
              onNavigateToMonth={(year, month) => {
                setInvoiceMonthFilter({ year, month });
                setActiveTab("invoices");
              }}
            />
          </TabsContent>

          <TabsContent value="suppliers" className="mt-6">
            {projectSuppliersQ.isLoading || supplierExclusionsQ.isLoading ? (
              <Skeleton className="h-32" />
            ) : (projectSuppliersQ.data ?? []).length === 0 ? (
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
                      <th className="px-4 py-2 font-medium w-12 text-center" title="Снимите чекбокс, чтобы исключить поставщика из расчётов">В расчётах</th>
                      <th className="px-4 py-2 font-medium">Поставщик</th>
                      <th className="px-4 py-2 font-medium text-right">Счетов</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(projectSuppliersQ.data ?? []).map((s) => {
                      const excluded = supplierExclusionsQ.data?.has(s.id) ?? false;
                      const isPopoverOpen = exclusionPopover?.supplierId === s.id;
                      const isThisRowPending =
                        toggleExclusion.isPending &&
                        toggleExclusion.variables?.supplierId === s.id;
                      // Disable all checkboxes while any toggle is in flight to prevent race conditions
                      const isAnyPending = toggleExclusion.isPending;
                      return (
                        <tr
                          key={s.id}
                          className="border-b border-border-subtle last:border-0 hover:bg-surface-hover"
                        >
                          <td className="px-4 py-2 text-center">
                            {isThisRowPending ? (
                              <Loader2 className="mx-auto size-4 animate-spin text-fg-tertiary" />
                            ) : (
                              <Checkbox
                                checked={!excluded}
                                disabled={isAnyPending}
                                aria-label={excluded ? `Включить ${s.name} в расчёты` : `Исключить ${s.name} из расчётов`}
                                onCheckedChange={(checked: boolean) => {
                                  if (checked) {
                                    toggleExclusion.mutate({ supplierId: s.id, excluded: false });
                                  } else {
                                    setExclusionPopover({ supplierId: s.id, reason: "" });
                                  }
                                }}
                              />
                            )}
                          </td>
                          <td className="px-4 py-2 text-fg">
                            <div>
                              <span className={excluded ? "text-fg-tertiary line-through" : ""}>
                                {s.name}
                              </span>
                              {s.inn && (
                                <span className="ml-2 text-xs text-fg-tertiary">
                                  ИНН {s.inn}
                                </span>
                              )}
                            </div>
                            {isPopoverOpen && (
                              <div className="mt-2 p-3 rounded-lg border border-border-subtle bg-surface shadow-md space-y-2">
                                <label
                                  htmlFor={`exclusion-reason-${s.id}`}
                                  className="text-xs text-fg-secondary"
                                >
                                  Причина исключения (необязательно)
                                </label>
                                <input
                                  id={`exclusion-reason-${s.id}`}
                                  autoFocus
                                  className="w-full rounded border border-border-subtle px-2 py-1 text-sm bg-bg text-fg focus:outline-none focus:ring-1 focus:ring-accent"
                                  placeholder="Аварийная закупка, нерепрезентативная цена..."
                                  value={exclusionPopover.reason}
                                  onChange={(e) =>
                                    setExclusionPopover((prev) =>
                                      prev ? { ...prev, reason: e.target.value } : null
                                    )
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === "Escape") setExclusionPopover(null);
                                    if (e.key === "Enter") {
                                      toggleExclusion.mutate({
                                        supplierId: s.id,
                                        excluded: true,
                                        reason: exclusionPopover.reason || undefined,
                                      });
                                      setExclusionPopover(null);
                                    }
                                  }}
                                />
                                <div className="flex gap-2 justify-end">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setExclusionPopover(null)}
                                  >
                                    Отмена
                                  </Button>
                                  <Button
                                    size="sm"
                                    onClick={() => {
                                      toggleExclusion.mutate({
                                        supplierId: s.id,
                                        excluded: true,
                                        reason: exclusionPopover.reason || undefined,
                                      });
                                      setExclusionPopover(null);
                                    }}
                                  >
                                    Исключить
                                  </Button>
                                </div>
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-fg-secondary">
                            {s.invoice_count}
                          </td>
                        </tr>
                      );
                    })}
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
