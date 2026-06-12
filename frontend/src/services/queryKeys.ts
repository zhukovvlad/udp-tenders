import type { ID } from "@/types/common";

export const qk = {
  projects: { all: ["projects"] as const },
  materialClasses: { all: ["material-classes"] as const },
  referencePrices: {
    // No args → bare base key; prefix invalidations in queries.ts rely on this shape.
    // With projectId → direction slot is always in a fixed position (like dashboard keys).
    all: (projectId?: ID, materialClassId?: ID, direction?: string) => {
      const base = ["reference-prices"] as const;
      if (!projectId) return base;
      return [
        ...base,
        projectId,
        ...(materialClassId ? [{ materialClassId }] : []),
        direction ?? "all",
      ] as const;
    },
  },
  documents: {
    list: (projectId?: ID) =>
      projectId ? (["documents", projectId] as const) : (["documents"] as const),
    detail: (docId: ID) => ["document", docId] as const,
  },
  dashboard: {
    summary: (projectId: ID) => ["dashboard", "summary", projectId] as const,
    invoices: (projectId: ID, direction?: string) =>
      ["dashboard", "invoices", projectId, direction ?? "all"] as const,
    calculations: (projectId: ID, periodStart?: string, periodEnd?: string, direction?: string) =>
      ["dashboard", "calculations", projectId, periodStart, periodEnd, direction ?? "all"] as const,
    calculationsAll: ["dashboard", "calculations", "all"] as const,
    monthly: (projectId: ID, direction?: string) =>
      ["dashboard", "monthly", projectId, direction ?? "all"] as const,
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
  projectSuppliers: (projectId: ID, direction?: string) =>
    ["project-suppliers", projectId, direction ?? "all"] as const,
  supplierExclusions: (projectId: ID) => ["supplier-exclusions", projectId] as const,
  corridors: (projectId: ID) => ["corridors", projectId] as const,
  units: { all: ["units"] as const },
  materialTypes: { all: ["material-types"] as const },
};
