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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Номер</TableHead>
          <TableHead>Дата</TableHead>
          <TableHead>Поставщик</TableHead>
          <TableHead>Позиции</TableHead>
          <TableHead className="text-right">Сумма</TableHead>
          <TableHead>ИИ</TableHead>
          <TableHead className="w-12"></TableHead>
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
                      className="text-warning"
                      aria-label="Требует проверки"
                    />
                  )}
                  {inv.number}
                </div>
              </TableCell>
              <TableCell className="text-fg-secondary">{formatDate(inv.date)}</TableCell>
              <TableCell>{inv.supplier_name || "—"}</TableCell>
              <TableCell className="max-w-md">
                <div className="space-y-0.5">
                  {inv.items.slice(0, 3).map((it, i) => (
                    <div key={i} className="truncate text-xs text-fg-secondary">
                      {it.material_class || it.item_type} ·{" "}
                      <span className="text-fg-tertiary">
                        {it.raw_name?.slice(0, 50)}
                        {(it.raw_name?.length ?? 0) > 50 ? "…" : ""}
                      </span>
                    </div>
                  ))}
                  {inv.items.length > 3 && (
                    <div className="text-xs text-fg-tertiary">
                      и ещё {inv.items.length - 3}
                    </div>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-right">
                <MoneyCell value={total} />
              </TableCell>
              <TableCell>
                <ConfidenceBadge value={inv.ai_confidence} />
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
  );
}
