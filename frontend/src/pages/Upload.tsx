import { useState } from "react";
import { toast } from "sonner";

import { Label } from "@/components/ui/label";

import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { Dropzone } from "@/components/ui-domain/Dropzone";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { EntitySelect } from "@/components/ui-domain/EntitySelect";
import { UploadJobRow, type JobState } from "@/components/upload/UploadJobRow";

import { useProjects, useUploadInvoice } from "@/services/queries";
import type { ID } from "@/types/common";

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
        if (result.duplicate) {
          toast.info(`«${job.file.name}» — файл уже был загружен`);
        } else {
          toast.success(`«${job.file.name}» принят в обработку`);
        }
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
            <EntitySelect
              items={projectsQ.data}
              value={projectId}
              onChange={(v) => setProjectId(v as number | null)}
              getLabel={(p) => p.name}
              placeholder="Выберите объект"
              className="w-[320px]"
            />
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
              <UploadJobRow key={j.id} job={j} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
