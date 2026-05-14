import { http, HttpResponse } from "msw";
import {
  sampleProject,
  sampleMaterialClass,
  sampleDocument,
  sampleDashboardSummary,
  sampleDashboardInvoices,
  sampleReferencePrice,
} from "./fixtures";

// Mutable state so that verify/unverify mutations are reflected in subsequent GETs.
// Keyed by invoice id (as string) so each invoice's state is independent.
const invoiceVerifiedById = new Map<string, boolean>();

export function resetHandlerState() {
  invoiceVerifiedById.clear();
}

export function setHandlerVerified(invoiceId: number | string, v: boolean) {
  invoiceVerifiedById.set(String(invoiceId), v);
}

export const handlers = [
  http.get("/api/health", () => HttpResponse.json({ status: "ok" })),

  http.get("/api/projects", () => HttpResponse.json([sampleProject])),
  http.post("/api/projects", () => HttpResponse.json(sampleProject)),
  http.put("/api/projects/:id", () => HttpResponse.json(sampleProject)),
  http.delete("/api/projects/:id", () => HttpResponse.json({ message: "Удалено" })),

  http.get("/api/material-classes", () => HttpResponse.json([sampleMaterialClass])),
  http.post("/api/material-classes", () => HttpResponse.json(sampleMaterialClass)),

  http.get("/api/reference-prices", () => HttpResponse.json([])),
  http.post("/api/reference-prices", () => HttpResponse.json({ id: 1 })),
  http.patch("/api/reference-prices/:id", () => HttpResponse.json(sampleReferencePrice)),
  http.delete("/api/reference-prices/:id", () => HttpResponse.json({ message: "Удалено" })),

  http.get("/api/invoices/documents", () => HttpResponse.json([sampleDocument])),
  http.get("/api/invoices/documents/:id", () => {
    const inv0 = sampleDocument.invoices[0];
    const verified = invoiceVerifiedById.get(String(inv0.id)) ?? false;
    return HttpResponse.json({
      ...sampleDocument,
      invoices: [{
        ...inv0,
        verified,
        verified_at: verified ? "2026-05-14T12:00:00" : null,
      }],
    });
  }),
  http.post("/api/invoices/upload", () => HttpResponse.json(sampleDocument)),
  http.post("/api/invoices/documents/:id/reparse", () => HttpResponse.json(sampleDocument)),
  http.put("/api/invoices/:id", ({ params }) =>
    HttpResponse.json({ message: "Сохранено", invoice_id: Number(params.id) })
  ),
  http.delete("/api/invoices/:id", () => HttpResponse.json({ message: "СФ удалена" })),
  http.delete("/api/invoices/documents/:id", () =>
    HttpResponse.json({ message: "Удалено" })
  ),
  http.post("/api/invoices/:id/verify", ({ params }) => {
    const id = String(params.id);
    invoiceVerifiedById.set(id, true);
    return HttpResponse.json({ message: "Проверено", invoice_id: Number(id), verified_at: "2026-05-14T12:00:00" });
  }),
  http.post("/api/invoices/:id/unverify", ({ params }) => {
    const id = String(params.id);
    invoiceVerifiedById.set(id, false);
    return HttpResponse.json({ message: "Отметка снята", invoice_id: Number(id) });
  }),

  http.get("/api/dashboard/summary", () => HttpResponse.json(sampleDashboardSummary)),
  http.get("/api/dashboard/invoices", () => HttpResponse.json(sampleDashboardInvoices)),
  http.get("/api/dashboard/calculations", () => HttpResponse.json([])),
  http.post("/api/dashboard/calculate", () =>
    HttpResponse.json({ message: "Рассчитано классов: 1", results: [] })
  ),
  http.post("/api/dashboard/auto-calculate", () =>
    HttpResponse.json({ message: "OK", period_start: null, period_end: null, results: [] })
  ),

  http.get("/api/settings", () =>
    HttpResponse.json({
      api_key_set: true,
      model: "anthropic/claude-sonnet-4.6",
      confidence_threshold: 0.7,
    })
  ),
  http.put("/api/settings", () => HttpResponse.json({ message: "Настройки сохранены" })),
];
