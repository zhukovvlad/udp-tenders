import { Trash2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui-domain/Button";
import { MoneyCell } from "@/components/ui-domain/MoneyCell";
import { useMaterialClasses } from "@/services/queries";
import type { InvoiceItem } from "@/types/invoice";

interface ReviewItemsTableProps {
  items: InvoiceItem[];
  onChange: (items: InvoiceItem[]) => void;
}

export function ReviewItemsTable({ items, onChange }: ReviewItemsTableProps) {
  const classes = useMaterialClasses();

  const update = (idx: number, patch: Partial<InvoiceItem>) => {
    onChange(items.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  };
  const remove = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      {items.map((it, i) => (
        <div
          key={it.id ?? `new-${i}`}
          className="grid grid-cols-12 gap-2 rounded-md border border-border-subtle bg-surface p-2"
        >
          <div className="col-span-4">
            <Input
              value={it.raw_name}
              onChange={(e) => update(i, { raw_name: e.target.value })}
              placeholder="Наименование"
            />
          </div>
          <div className="col-span-2">
            <Select
              value={it.material_class_id ? String(it.material_class_id) : ""}
              onValueChange={(v: string | null) =>
                update(i, { material_class_id: v ? Number(v) : null })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Класс" />
              </SelectTrigger>
              <SelectContent>
                {(classes.data ?? []).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-1">
            <Input
              type="number"
              value={it.quantity}
              onChange={(e) =>
                update(i, { quantity: Number(e.target.value) || 0 })
              }
            />
          </div>
          <div className="col-span-1">
            <Input
              value={it.unit}
              onChange={(e) => update(i, { unit: e.target.value })}
              placeholder="ед."
            />
          </div>
          <div className="col-span-2">
            <Input
              type="number"
              value={it.unit_price}
              onChange={(e) =>
                update(i, { unit_price: Number(e.target.value) || 0 })
              }
              placeholder="цена"
            />
          </div>
          <div className="col-span-1 flex items-center justify-end pr-1 text-sm">
            <MoneyCell value={it.amount} />
          </div>
          <div className="col-span-1 flex items-center justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => remove(i)}
              aria-label="Удалить позицию"
            >
              <Trash2 size={14} />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
