import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle, Loader2, FileText } from "lucide-react";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { Dropzone } from "@/components/ui-domain/Dropzone";
import { StatusPill } from "@/components/ui-domain/StatusPill";
import { ConfidenceBadge } from "@/components/ui-domain/ConfidenceBadge";
import { Button } from "@/components/ui-domain/Button";
import { EmptyState } from "@/components/ui-domain/EmptyState";

import { useProjects, useUploadInvoice } from "@/services/queries";
import type { ID } from "@/types/common";
import type { DocumentDetail } from "@/types/invoice";

interface JobState {
  id: string;
  file: File;
  status: "pending" | "uploading" | "ready" | "error";
  progress: number;
  result?: DocumentDetail;
  error?: string;
}

export default function UploadPage() {
  const projectsQ = useProjects();
  const upload = useUploadInvoice();

  const [projectId, setProjectId] = useState<ID | null>(null);
  const [jobs, setJobs] = useState<JobState[]>([]);

  const handleDrop = async (files: File[]) => {
    if (!projectId) return;
    const newJobs: JobState[] = files.map((f, i) => ({
      id: `${Date.now()}-${i}-${f.name}`,
      file: f,
      status: "pending",
      progress: 0,
    }));
    setJobs((prev) => [...newJobs, ...prev]);

    for (const job of newJobs) {
      setJobs((prev) =>
        prev.map((j) => (j.id === job.id ? { ...j, status: "uploading" } : j))
      );
      try {
        const result = await upload.mutateAsync({
          projectId,
          file: job.file,
          onProgress: (pct) =>
            setJobs((prev) =>
              prev.map((j) => (j.id === job.id ? { ...j, progress: pct } : j))
            ),
        });
        setJobs((prev) =>
          prev.map((j) =>
            j.id === job.id ? { ...j, status: "ready", result, progress: 100 } : j
          )
        );
        toast.success(`«${job.file.name}» загружен`);
      } catch (err) {
        setJobs((prev) =>
          prev.map((j) =>
            j.id === job.id
              ? {
                  ...j,
                  status: "error",
                  error: err instanceof Error ? err.message : "Ошибка загрузки",
                }
              : j
          )
        );
      }
    }
  };

  return (
    <div className="container-page py-8">
      <PageHeader
        serif
        title="Загрузка документов"
        subtitle="Перетащите счета-фактуры или УПД — система распарсит позиции автоматически"
      />

      {/* Контекст: объект */}
      <Surface className="mt-6">
        <div className="flex items-end gap-4">
          <div className="space-y-1.5">
            <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
              Объект *
            </Label>
            <Select
              value={projectId ? String(projectId) : ""}
              onValueChange={(v) => setProjectId(v ? Number(v) : null)}
            >
              <SelectTrigger className="w-[320px]">
                <SelectValue placeholder="Выберите объект" />
              </SelectTrigger>
              <SelectContent>
                {(projectsQ.data ?? []).map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </Surface>

      {/* Dropzone */}
      <div className="mt-4">
        {projectId ? (
          <Dropzone
            onDrop={handleDrop}
            multiple
            accept={{
              "application/pdf": [".pdf"],
              "image/jpeg": [".jpg", ".jpeg"],
              "image/png": [".png"],
            }}
          />
        ) : (
          <EmptyState
            title="Сначала выберите объект"
            description="К объекту привязываются загружаемые документы."
          />
        )}
      </div>

      {/* Список заданий */}
      {jobs.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 font-serif text-xl font-medium text-fg">
            История загрузки
          </h2>
          <div className="space-y-2">
            {jobs.map((j) => (
              <Surface key={j.id} padding="sm">
                <div className="flex items-start gap-4">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-surface-sunken">
                    {j.status === "uploading" && (
                      <Loader2 size={16} className="animate-spin text-accent" />
                    )}
                    {j.status === "ready" && (
                      <CheckCircle2 size={16} className="text-accent" />
                    )}
                    {j.status === "error" && (
                      <AlertTriangle size={16} className="text-danger" />
                    )}
                    {j.status === "pending" && (
                      <FileText size={16} className="text-fg-tertiary" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-fg">
                        {j.file.name}
                      </span>
                      {j.status === "uploading" && (
                        <StatusPill tone="info" label={`${j.progress}%`} />
                      )}
                      {j.status === "ready" && (
                        <StatusPill tone="success" label="готово" dot />
                      )}
                      {j.status === "error" && (
                        <StatusPill tone="danger" label="ошибка" dot />
                      )}
                    </div>
                    {j.result && (
                      <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-fg-secondary">
                        {j.result.invoices.map((inv) => (
                          <span key={inv.id} className="flex items-center gap-1.5">
                            СФ № {inv.number} · {inv.items.length} позиций
                            <ConfidenceBadge value={inv.ai_confidence} />
                          </span>
                        ))}
                      </div>
                    )}
                    {j.error && (
                      <div className="mt-1 text-xs text-danger-text">{j.error}</div>
                    )}
                  </div>
                  {j.result && (
                    <Link to={`/documents/${j.result.id}`}>
                      <Button variant="secondary" size="sm">
                        Проверить
                      </Button>
                    </Link>
                  )}
                </div>
              </Surface>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
