import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Breadcrumbs } from "@/components/ui-domain/Breadcrumbs";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { Button } from "@/components/ui-domain/Button";
import { InvoiceTable } from "@/components/invoices/InvoiceTable";

import {
  useProjects,
  useDashboardInvoices,
  useDashboardSummary,
} from "@/services/queries";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import { KpiCard } from "@/components/ui-domain/KpiCard";

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id ? Number(id) : null;

  const projectsQ = useProjects();
  const project = projectsQ.data?.find((p) => p.id === projectId) ?? null;

  const summaryQ = useDashboardSummary(projectId);
  const invoicesQ = useDashboardInvoices(projectId);

  if (projectsQ.isLoading) {
    return (
      <div className="container-page py-8 space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-[120px]" />
      </div>
    );
  }

  if (!project) {
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

  return (
    <div className="container-page py-8">
      <Breadcrumbs
        items={[
          { label: "Объекты", to: "/projects" },
          { label: project.name },
        ]}
      />
      <PageHeader
        serif
        title={project.name}
        subtitle={
          project.contract_number
            ? `Договор № ${project.contract_number} · создан ${formatDate(project.created_at)}`
            : `Создан ${formatDate(project.created_at)}`
        }
      />

      {summaryQ.data && (
        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Документов" value={formatNumber(summaryQ.data.doc_count)} />
          <KpiCard label="СФ" value={formatNumber(summaryQ.data.invoice_count)} />
          <KpiCard label="Объём, м³" value={formatNumber(summaryQ.data.total_qty)} />
          <KpiCard label="Сумма" value={formatMoney(summaryQ.data.total_amount)} />
        </div>
      )}

      <section className="mt-8">
        <h2 className="mb-3 font-serif text-xl font-medium text-fg">
          Счета-фактуры
        </h2>
        {invoicesQ.isLoading ? (
          <Surface padding="none">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </Surface>
        ) : (invoicesQ.data ?? []).length === 0 ? (
          <EmptyState
            title="Нет счетов-фактур"
            description="Загрузите документы, чтобы они появились здесь."
            action={
              <Link to="/upload">
                <Button>Загрузить документ</Button>
              </Link>
            }
          />
        ) : (
          <Surface padding="none">
            <InvoiceTable invoices={invoicesQ.data ?? []} />
          </Surface>
        )}
      </section>
    </div>
  );
}
