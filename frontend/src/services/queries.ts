import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { projectsApi } from "./api/projects";
import { materialClassesApi } from "./api/materialClasses";
import { referencePricesApi } from "./api/referencePrices";
import { invoicesApi } from "./api/invoices";
import { dashboardApi } from "./api/dashboard";
import { uploadApi } from "./api/upload";
import { settingsApi } from "./api/settings";
import { qk } from "./queryKeys";

import type { ID } from "@/types/common";
import type { ProjectCreateInput, ProjectUpdateInput } from "@/types/project";
import type { MaterialClassCreateInput } from "@/types/materialClass";
import type { ReferencePriceCreateInput } from "@/types/referencePrice";
import type { InvoiceUpdateInput } from "@/types/invoice";
import type { CalculateInput } from "@/types/dashboard";
import type { AppSettings } from "./api/settings";

// ========== Projects ==========
export function useProjects() {
  return useQuery({ queryKey: qk.projects.all, queryFn: projectsApi.list });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ProjectCreateInput) => projectsApi.create(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.projects.all });
      toast.success("Объект создан");
    },
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: ID; input: ProjectUpdateInput }) =>
      projectsApi.update(id, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.projects.all });
      toast.success("Объект обновлён");
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => projectsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.projects.all });
      toast.success("Объект удалён");
    },
  });
}

// ========== Material classes ==========
export function useMaterialClasses() {
  return useQuery({
    queryKey: qk.materialClasses.all,
    queryFn: materialClassesApi.list,
  });
}

export function useCreateMaterialClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: MaterialClassCreateInput) =>
      materialClassesApi.create(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.materialClasses.all });
      toast.success("Класс материала добавлен");
    },
  });
}

export function useDeleteMaterialClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => materialClassesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.materialClasses.all });
      toast.success("Класс материала удалён");
    },
  });
}

// ========== Reference prices ==========
export function useReferencePrices(projectId?: ID) {
  return useQuery({
    queryKey: qk.referencePrices.all(projectId),
    queryFn: () => referencePricesApi.list(projectId),
  });
}

export function useCreateReferencePrice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ReferencePriceCreateInput) =>
      referencePricesApi.create(input),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.referencePrices.all() });
      qc.invalidateQueries({ queryKey: qk.referencePrices.all(input.project_id) });
      toast.success("Эталон сохранён");
    },
  });
}

export function useDeleteReferencePrice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => referencePricesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.referencePrices.all() });
      toast.success("Эталон удалён");
    },
  });
}

// ========== Documents / Invoices ==========
export function useDocument(docId: ID | null | undefined) {
  return useQuery({
    queryKey: qk.documents.detail(docId ?? -1),
    queryFn: () => invoicesApi.getDocument(docId as ID),
    enabled: docId !== null && docId !== undefined,
  });
}

export function useReparseDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: ID) => invoicesApi.reparseDocument(docId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: qk.documents.detail(data.id) });
      toast.success("Документ переразобран");
    },
  });
}

export function useUpdateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: ID; input: InvoiceUpdateInput }) =>
      invoicesApi.update(id, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["document"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("СФ сохранена");
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: ID) => invoicesApi.removeDocument(docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Документ удалён");
    },
  });
}

// ========== Dashboard ==========
export function useDashboardSummary(projectId: ID | null) {
  return useQuery({
    queryKey: projectId ? qk.dashboard.summary(projectId) : ["dashboard", "summary", "none"],
    queryFn: () => dashboardApi.summary(projectId as ID),
    enabled: projectId !== null,
  });
}

export function useDashboardInvoices(projectId: ID | null) {
  return useQuery({
    queryKey: projectId ? qk.dashboard.invoices(projectId) : ["dashboard", "invoices", "none"],
    queryFn: () => dashboardApi.invoices(projectId as ID),
    enabled: projectId !== null,
  });
}

export function useDashboardCalculations(projectId: ID | null) {
  return useQuery({
    queryKey: projectId
      ? qk.dashboard.calculations(projectId)
      : ["dashboard", "calculations", "none"],
    queryFn: () => dashboardApi.calculations(projectId as ID),
    enabled: projectId !== null,
  });
}

export function useAutoCalculate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: ID) => dashboardApi.autoCalculate(projectId),
    onSuccess: (_data, projectId) => {
      qc.invalidateQueries({ queryKey: qk.dashboard.calculations(projectId) });
      qc.invalidateQueries({ queryKey: qk.dashboard.calculationsAll });
    },
  });
}

export function useCalculate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CalculateInput) => dashboardApi.calculate(input),
    onSuccess: (_d, input) => {
      qc.invalidateQueries({ queryKey: qk.dashboard.calculations(input.project_id) });
      qc.invalidateQueries({ queryKey: qk.dashboard.calculationsAll });
      toast.success("Расчёт выполнен");
    },
  });
}

// ========== Upload ==========
export function useUploadInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      file,
      onProgress,
    }: {
      projectId: ID;
      file: File;
      onProgress?: (pct: number) => void;
    }) => uploadApi.uploadInvoice(projectId, file, onProgress),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// ========== Settings ==========
export function useSettings() {
  return useQuery({ queryKey: qk.settings.current, queryFn: settingsApi.get });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<AppSettings>) => settingsApi.update(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.settings.current });
      toast.success("Настройки сохранены");
    },
  });
}

// ========== Documents ==========
export function useDocuments(projectId?: number) {
  return useQuery({
    queryKey: qk.documents.list(projectId),
    queryFn: () => invoicesApi.listDocuments(projectId),
  });
}

// ========== Dashboard (all projects) ==========
export function useAllCalculations() {
  return useQuery({
    queryKey: qk.dashboard.calculationsAll,
    queryFn: () => dashboardApi.calculationsAll(),
    staleTime: 0,
  });
}
