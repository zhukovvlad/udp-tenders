import { useState, useCallback } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dropzone } from "@/components/ui-domain/Dropzone";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { uploadApi } from "@/services/api/upload";
import { qk } from "@/services/queryKeys";
import type { ID } from "@/types/common";

interface UploadStatus {
  fileName: string;
  fileIndex: number;
  fileCount: number;
  /** 0–100 during HTTP transfer; null while AI analyzes */
  uploadPct: number | null;
}

interface Props {
  projectId: ID;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadSheet({ projectId, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<UploadStatus | null>(null);

  const handleDrop = useCallback(async (files: File[]) => {
    let success = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setStatus({ fileName: file.name, fileIndex: i + 1, fileCount: files.length, uploadPct: 0 });
      try {
        await uploadApi.uploadInvoice(projectId, file, (pct) => {
          setStatus((prev) =>
            prev ? { ...prev, uploadPct: pct < 100 ? pct : null } : prev
          );
        });
        success++;
      } catch {
        toast.error(`Ошибка загрузки: ${file.name}`);
      }
    }
    setStatus(null);
    if (success > 0) {
      qc.invalidateQueries({ queryKey: ["dashboard", "invoices", projectId] });
      qc.invalidateQueries({ queryKey: qk.dashboard.summary(projectId) });
      qc.invalidateQueries({ queryKey: qk.documents.list() });
      toast.success(`Загружено: ${success} файл(ов)`);
      onOpenChange(false);
    }
  }, [projectId, qc, onOpenChange]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-[480px]">
        <SheetHeader>
          <SheetTitle>Добавить счёт</SheetTitle>
        </SheetHeader>
        <div className="mt-6">
          <Dropzone onDrop={handleDrop} disabled={status !== null} />
          {status && <UploadProgress status={status} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function UploadProgress({ status }: { status: UploadStatus }) {
  const { fileName, fileIndex, fileCount, uploadPct } = status;
  const isAnalyzing = uploadPct === null;

  return (
    <div className="mt-5 space-y-3">
      <div className="flex items-center justify-between text-xs text-fg-secondary">
        <span className="max-w-[280px] truncate font-medium text-fg">{fileName}</span>
        {fileCount > 1 && (
          <span>{fileIndex} / {fileCount}</span>
        )}
      </div>

      {/* Progress bar */}
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-hover"
        aria-busy={isAnalyzing}
      >
        {isAnalyzing ? (
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuetext="Анализируем документ с помощью ИИ…"
            className="h-full w-2/5 animate-indeterminate rounded-full bg-accent"
          />
        ) : (
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={uploadPct ?? 0}
            className="h-full rounded-full bg-accent transition-all duration-200"
            style={{ width: `${uploadPct}%` }}
          />
        )}
      </div>

      <p aria-live="polite" className="text-xs text-fg-secondary">
        {isAnalyzing
          ? "Анализируем документ с помощью ИИ…"
          : `Отправка файла… ${uploadPct}%`}
      </p>
    </div>
  );
}
