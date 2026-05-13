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
    calculations: (projectId: ID) =>
      ["dashboard", "calculations", projectId] as const,
    calculationsAll: ["dashboard", "calculations", "all"] as const,
  },
  settings: { current: ["settings"] as const },
};
