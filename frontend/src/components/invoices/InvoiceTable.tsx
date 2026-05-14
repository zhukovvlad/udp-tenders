import { Link } from "react-router-dom";
import { FileEdit } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui-domain/Button";
import { StatusPill } from "@/components/ui-domain/StatusPill";
import { MoneyCell } from "@/components/ui-domain/MoneyCell";
import { formatDate } from "@/lib/format";
import type { DashboardInvoiceRow } from "@/types/invoice";

interface InvoiceTableProps {
  invoices: DashboardInvoiceRow[];
  confidenceThreshold?: number;
}

type Stage = "confirmed" | "review" | "pending";

// Граница уверенности ИИ, ниже которой счёт требует ручного разбора.
// Совпадает с порогом в ConfidenceBadge / ReviewIssues.
const REVIEW_CONFIDENCE_THRESHOLD = 0.70;

function getStage(inv: DashboardInvoiceRow, threshold: number): Stage {
  if (inv.verified) return "confirmed";
  if (
    inv.has_issues ||
    !inv.supplier_name ||
    !inv.number ||
    (inv.ai_confidence ?? 0) < threshold
  )
    return "review";
  return "pending";
}

const STAGE_CONFIG: Record<Stage, { tone: "success" | "danger" | "neutral"; label: string }> = {
  confirmed: { tone: "success", label: "Подтверждён" },
  review:    { tone: "danger",  label: "Разобрать" },
  pending:   { tone: "neutral", label: "Ожидает" },
};

export function InvoiceTable({ invoices, confidenceThreshold = REVIEW_CONFIDENCE_THRESHOLD }: InvoiceTableProps) {
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[860px] table-fixed">
        <colgroup>
          <col className="w-[5rem]" />
          <col className="w-[6.5rem]" />
          <col className="w-[13rem]" />
          <col />
          <col className="w-[9.5rem]" />
          <col className="w-[7.5rem]" />
          <col className="w-[3.5rem]" />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead>Номер</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Поставщик</TableHead>
            <TableHead>Позиции</TableHead>
            <TableHead className="text-right">Сумма</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((inv) => {
            const total = inv.items.reduce((s, it) => s + it.amount, 0);
            const stage = getStage(inv, confidenceThreshold);
            const { tone, label } = STAGE_CONFIG[stage];
            const confidencePct =
              inv.ai_confidence !== null && inv.ai_confidence !== undefined
                ? `ИИ: ${Math.round(inv.ai_confidence * 100)}%`
                : null;
            const tooltip = [label, confidencePct].filter(Boolean).join(" · ");
            return (
              <TableRow key={inv.id} className="hover:bg-surface-hover">
                <TableCell className={`font-medium overflow-hidden border-l-2 ${stage === "review" ? "border-danger" : "border-transparent"}`}>
                  <span className="block whitespace-normal break-all" title={inv.number}>{inv.number}</span>
                </TableCell>
                <TableCell className="text-fg-secondary tabular-nums">
                  {formatDate(inv.date)}
                </TableCell>
                <TableCell className="truncate" title={inv.supplier_name ?? ""}>
                  {inv.supplier_name || "—"}
                </TableCell>
                <TableCell>
                  <div className="space-y-0.5">
                    {inv.items.slice(0, 3).map((it, i) => (
                      <div
                        key={i}
                        className="truncate text-xs text-fg-secondary"
                        title={it.raw_name ?? ""}
                      >
                        <span className="text-fg-tertiary">
                          {it.material_class || it.item_type}
                        </span>
                        {" · "}
                        {it.raw_name}
                      </div>
                    ))}
                    {inv.items.length > 3 && (
                      <div className="text-xs text-fg-tertiary">
                        и ещё {inv.items.length - 3}
                      </div>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  <MoneyCell value={total} />
                </TableCell>
                <TableCell>
                  <span title={tooltip} aria-label={tooltip}>
                    <StatusPill tone={tone} label={label} dot />
                  </span>
                </TableCell>
                <TableCell>
                  <Link to={`/documents/${inv.document_id}`}>
                    <Button variant="ghost" size="sm" aria-label="Редактировать">
                      <FileEdit size={14} />
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
