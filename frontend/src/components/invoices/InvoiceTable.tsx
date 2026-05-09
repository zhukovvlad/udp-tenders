import { Link } from "react-router-dom";
import { AlertTriangle, FileEdit } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui-domain/Button";
import { ConfidenceBadge } from "@/components/ui-domain/ConfidenceBadge";
import { MoneyCell } from "@/components/ui-domain/MoneyCell";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { InvoiceRow } from "@/types/invoice";

interface InvoiceTableProps {
  invoices: InvoiceRow[];
}

export function InvoiceTable({ invoices }: InvoiceTableProps) {
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[960px] table-fixed">
        <colgroup>
          <col className="w-[7rem]" />
          <col className="w-[6.5rem]" />
          <col className="w-[12rem]" />
          <col />
          <col className="w-[8rem]" />
          <col className="w-[4.5rem]" />
          <col className="w-[3rem]" />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead>Номер</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Поставщик</TableHead>
            <TableHead>Позиции</TableHead>
            <TableHead className="text-right">Сумма</TableHead>
            <TableHead>ИИ</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((inv) => {
            const total = inv.items.reduce((s, it) => s + it.amount, 0);
            return (
              <TableRow
                key={inv.id}
                className={cn(
                  "hover:bg-surface-hover",
                  inv.has_issues && "bg-warning-soft"
                )}
              >
                <TableCell className="font-medium">
                  <div className="flex items-center gap-1.5">
                    {inv.has_issues && (
                      <AlertTriangle
                        size={14}
                        className="shrink-0 text-warning"
                        aria-label="Требует проверки"
                      />
                    )}
                    <span className="truncate">{inv.number}</span>
                  </div>
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
                          {it.material_class?.name || it.item_type}
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
                  <ConfidenceBadge value={inv.ai_confidence} />
                </TableCell>
                <TableCell className="text-right">
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
