import type { ID } from "@/types/common";

export const qk = {
  projects: { all: ["projects"] as const },
  materialClasses: { all: ["material-classes"] as const },
  referencePrices: {
    all: (projectId?: ID, materialClassId?: ID) => {
      const base = ["reference-prices"] as const;
      if (!projectId && !materialClassId) return base;
      return [...base, ...(projectId ? [projectId] : []), ...(materialClassId ? [{ materialClassId }] : [])] as const;
    },
  },
  documents: {
    list: (projectId?: ID) =>
      projectId ? (["documents", projectId] as const) : (["documents"] as const),
    detail: (docId: ID) => ["document", docId] as const,
  },
  dashboard: {
    summary: (projectId: ID) => ["dashboard", "summary", projectId] as const,
    invoices: (projectId: ID) => ["dashboard", "invoices", projectId] as const,
    calculations: (projectId: ID, periodStart?: string, periodEnd?: string) =>
      ["dashboard", "calculations", projectId, periodStart, periodEnd] as const,
    calculationsAll: ["dashboard", "calculations", "all"] as const,
    monthly: (projectId: ID) => ["dashboard", "monthly", projectId] as const,
  },
  suppliers: {
    all: ["suppliers"] as const,
    detail: (id: ID) => ["suppliers", id] as const,
    projects: (id: ID) => ["suppliers", id, "projects"] as const,
    invoices: (id: ID, projectId?: ID) =>
      projectId !== undefined
        ? (["suppliers", id, "invoices", projectId] as const)
        : (["suppliers", id, "invoices"] as const),
  },
  settings: { current: ["settings"] as const },
  admin: {
    organizations: ["admin", "organizations"] as const,
    organization: (id: ID) => ["admin", "organizations", id] as const,
    users: (q?: string, page?: number, pageSize?: number) =>
      ["admin", "users", q ?? "", page ?? 1, pageSize ?? 20] as const,
  },
  projectSuppliers: (projectId: ID) => ["project-suppliers", projectId] as const,
  supplierExclusions: (projectId: ID) => ["supplier-exclusions", projectId] as const,
  corridors: (projectId: ID) => ["corridors", projectId] as const,
  units: { all: ["units"] as const },
  materialTypes: { all: ["material-types"] as const },
};
