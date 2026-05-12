import { useState, useCallback } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dropzone } from "@/components/ui-domain/Dropzone";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { uploadApi } from "@/services/api/upload";
import { qk } from "@/services/queryKeys";
import type { ID } from "@/types/common";

interface Props {
  projectId: ID;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadSheet({ projectId, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);

  const handleDrop = useCallback(async (files: File[]) => {
    setUploading(true);
    let success = 0;
    for (const file of files) {
      try {
        await uploadApi.uploadInvoice(projectId, file);
        success++;
      } catch {
        toast.error(`Ошибка загрузки: ${file.name}`);
      }
    }
    setUploading(false);
    if (success > 0) {
      qc.invalidateQueries({ queryKey: qk.dashboard.invoices(projectId) });
      qc.invalidateQueries({ queryKey: qk.dashboard.summary(projectId) });
      qc.invalidateQueries({ queryKey: qk.documents.list() });
      qc.invalidateQueries({ queryKey: qk.documents.list(projectId) });
      toast.success(`Загружено: ${success} файл(ов)`);
      onOpenChange(false);
    }
  }, [projectId, qc, onOpenChange]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Добавить счёт</SheetTitle>
        </SheetHeader>
        <div className="mt-6">
          <Dropzone onDrop={handleDrop} disabled={uploading} />
          {uploading && (
            <p className="mt-4 text-center text-sm text-fg-secondary">Загрузка…</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
