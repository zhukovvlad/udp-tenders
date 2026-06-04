import { useMemo, useState } from "react";
import { Surface } from "@/components/ui-domain/Surface";
import { Button } from "@/components/ui-domain/Button";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  useMaterialClasses,
  useCompensationCorridors,
  useSetCorridor,
  useDeleteCorridor,
} from "@/services/queries";
import type { ID } from "@/types/common";

export function CorridorsTab({ projectId }: { projectId: ID }) {
  const classesQ = useMaterialClasses();
  const corridorsQ = useCompensationCorridors(projectId);
  const setCorridor = useSetCorridor(projectId);
  const deleteCorridor = useDeleteCorridor(projectId);

  const [editingId, setEditingId] = useState<ID | null>(null);
  const [draft, setDraft] = useState("");

  const corridorByClass = useMemo(() => {
    const m = new Map<ID, number>();
    for (const c of corridorsQ.data ?? []) m.set(c.material_class_id, c.corridor_pct);
    return m;
  }, [corridorsQ.data]);

  if (classesQ.isLoading || corridorsQ.isLoading) {
    return <Skeleton className="h-40" />;
  }

  const classes = classesQ.data ?? [];

  function startEdit(id: ID, current: number | undefined) {
    setEditingId(id);
    setDraft(current != null ? String(current) : "");
  }

  function commit(id: ID) {
    const pct = parseFloat(draft.replace(",", "."));
    if (Number.isFinite(pct) && pct >= 0 && pct <= 100) {
      setCorridor.mutate({ materialClassId: id, corridorPct: pct });
    }
    setEditingId(null);
    setDraft("");
  }

  return (
    <Surface padding="none" className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="text-xs text-fg-tertiary hover:bg-transparent">
            <TableHead className="font-medium">Класс</TableHead>
            <TableHead className="font-medium text-right">Коридор, %</TableHead>
            <TableHead className="font-medium text-right">Действия</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {classes.map((mc) => {
            const pct = corridorByClass.get(mc.id);
            const isEditing = editingId === mc.id;
            return (
              <TableRow key={mc.id}>
                <TableCell className="text-fg">{mc.name}</TableCell>
                <TableCell className="text-right font-mono">
                  {isEditing ? (
                    <input
                      aria-label="Процент коридора"
                      autoFocus
                      className="w-20 rounded border border-border-subtle bg-surface px-2 py-1 text-right"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commit(mc.id);
                        if (e.key === "Escape") { setEditingId(null); setDraft(""); }
                      }}
                      onBlur={() => commit(mc.id)}
                    />
                  ) : pct != null ? (
                    `${pct}%`
                  ) : (
                    <span className="text-fg-tertiary">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {pct != null ? (
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(mc.id, pct)}>
                        Изменить
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteCorridor.mutate(mc.id)}
                      >
                        Снять
                      </Button>
                    </div>
                  ) : (
                    !isEditing && (
                      <Button variant="ghost" size="sm" onClick={() => startEdit(mc.id, undefined)}>
                        Сделать компенсируемым
                      </Button>
                    )
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Surface>
  );
}
