import { useState, useMemo, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { Tabs } from "@/components/ui-domain/Tabs";
import { Breadcrumbs } from "@/components/ui-domain/Breadcrumbs";
import { Button } from "@/components/ui-domain/Button";
import { StatusPill } from "@/components/ui-domain/StatusPill";
import { ConfidenceBadge } from "@/components/ui-domain/ConfidenceBadge";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";

import { ReviewHeader } from "@/components/review/ReviewHeader";
import { ReviewItemsTable } from "@/components/review/ReviewItemsTable";
import { ReviewIssues } from "@/components/review/ReviewIssues";

import {
  useDocument,
  useUpdateInvoice,
  useReparseDocument,
  useDeleteDocument,
} from "@/services/queries";
import { invoicesApi } from "@/services/api/invoices";
import { formatDate } from "@/lib/format";
import type { InvoiceRow } from "@/types/invoice";

type TabKey = "header" | "items" | "issues";

export default function Review() {
  const { id } = useParams<{ id: string }>();
  const docId = id ? Number(id) : null;
  const navigate = useNavigate();

  const docQ = useDocument(docId);
  const update = useUpdateInvoice();
  const reparse = useReparseDocument();
  const remove = useDeleteDocument();

  const [tab, setTab] = useState<TabKey>("items");
  const [draft, setDraft] = useState<InvoiceRow | null>(null);

  // Загрузить первый СФ документа в draft при первом получении
  useEffect(() => {
    const inv = docQ.data?.invoices[0];
    if (inv && (!draft || draft.id !== inv.id)) {
      setDraft(inv);
    }
  }, [docQ.data, draft]);

  const dirty = useMemo(() => {
    const inv = docQ.data?.invoices[0];
    if (!draft || !inv) return false;
    return JSON.stringify(draft) !== JSON.stringify(inv);
  }, [draft, docQ.data]);

  if (docId === null) {
    return (
      <div className="container-page py-8">
        <EmptyState title="Документ не найден" />
      </div>
    );
  }

  if (docQ.isLoading) {
    return (
      <div className="container-page py-8 space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  if (!docQ.data || !draft) {
    return (
      <div className="container-page py-8">
        <EmptyState title="Документ не найден" />
      </div>
    );
  }

  const doc = docQ.data;
  const inv = draft;

  const tabs: Array<{ value: TabKey; label: string }> = [
    { value: "header", label: "Шапка" },
    { value: "items", label: `Позиции · ${inv.items.length}` },
    { value: "issues", label: "Проблемы" },
  ];

  return (
    <div className="container-page py-6">
      <Breadcrumbs
        items={[
          { label: "Дашборд", to: "/" },
          { label: doc.filename },
          { label: `СФ № ${inv.number || "—"}` },
        ]}
      />

      <PageHeader
        title={`СФ № ${inv.number || "—"} от ${formatDate(inv.date)}`}
        subtitle={inv.supplier_name ?? "Поставщик не указан"}
        actions={
          <>
            <ConfidenceBadge value={inv.ai_confidence} />
            <StatusPill
              tone={inv.has_issues ? "warning" : "success"}
              label={inv.has_issues ? "требует проверки" : "готово"}
              dot
            />
          </>
        }
      />

      {/* Сверху — редактирование на всю ширину */}
      <div className="mt-6">
        <Tabs<TabKey> value={tab} onValueChange={setTab} tabs={tabs}>
          {tab === "header" && (
            <Surface>
              <ReviewHeader
                invoice={inv}
                onChange={(patch) => setDraft({ ...inv, ...patch })}
              />
            </Surface>
          )}
          {tab === "items" && (
            <ReviewItemsTable
              items={inv.items}
              onChange={(items) => setDraft({ ...inv, items })}
            />
          )}
          {tab === "issues" && (
            <Surface>
              <ReviewIssues invoice={inv} />
            </Surface>
          )}
        </Tabs>
      </div>

      {/* Снизу — превью оригинала документа */}
      <section className="mt-8">
        <div className="mb-3 flex items-end justify-between gap-3">
          <h2 className="font-serif text-xl font-medium text-fg">
            Оригинал документа
          </h2>
          <div className="flex items-center gap-3 text-xs text-fg-tertiary">
            <span>{doc.filename}</span>
            <button
              type="button"
              onClick={() => reparse.mutate(docId)}
              disabled={reparse.isPending}
              className="text-fg-secondary underline-offset-2 hover:text-fg hover:underline disabled:opacity-50"
            >
              Переразобрать
            </button>
          </div>
        </div>
        <Surface padding="none" className="overflow-hidden">
          <iframe
            title="Документ"
            src={invoicesApi.documentPdfUrl(docId)}
            className="h-[90vh] w-full border-0 bg-surface-sunken"
          />
        </Surface>
      </section>

      {/* Sticky-bar внизу */}
      <div className="sticky bottom-0 -mx-6 mt-8 border-t border-border-subtle bg-surface/95 px-6 py-3 backdrop-blur">
        <div className="container-page flex items-center justify-between">
          <Button
            variant="ghost"
            leftIcon={<ArrowLeft size={14} />}
            onClick={() => navigate(-1)}
          >
            Назад
          </Button>
          <div className="flex items-center gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                if (window.confirm("Удалить документ?")) {
                  remove.mutate(docId, {
                    onSuccess: () => navigate("/"),
                  });
                }
              }}
            >
              Удалить
            </Button>
            <Button
              variant="secondary"
              disabled={!dirty || update.isPending}
              loading={update.isPending}
              onClick={() =>
                update.mutate({
                  id: inv.id,
                  input: {
                    number: inv.number,
                    date: inv.date,
                    supplier_name: inv.supplier_name,
                    supplier_inn: inv.supplier_inn,
                    vat_rate: inv.vat_rate,
                    items: inv.items,
                  },
                })
              }
            >
              Сохранить
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
