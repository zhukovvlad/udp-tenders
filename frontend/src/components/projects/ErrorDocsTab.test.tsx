import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import { ErrorDocsTab } from "./ErrorDocsTab";
import type { DocumentSummary } from "@/types/invoice";

const makeDoc = (overrides: Partial<DocumentSummary> = {}): DocumentSummary => ({
  id: 1,
  project_id: 10,
  filename: "invoice-2024-01.pdf",
  doc_type: "invoice",
  status: "error",
  uploaded_at: "2024-01-15T10:00:00Z",
  invoice_count: 0,
  has_issues: false,
  ai_confidence: null,
  ...overrides,
});

describe("ErrorDocsTab", () => {
  it("shows positive empty state when no error docs", () => {
    const cleanDoc = makeDoc({ status: "parsed", has_issues: false });
    renderWithProviders(<ErrorDocsTab docs={[cleanDoc]} />);
    expect(screen.getByText(/все документы разобраны успешно/i)).toBeInTheDocument();
  });

  it("renders error doc row with filename", () => {
    renderWithProviders(<ErrorDocsTab docs={[makeDoc()]} />);
    expect(screen.getByText("invoice-2024-01.pdf")).toBeInTheDocument();
  });

  it("renders has_issues doc with 'Проблемы в СФ' status", () => {
    const doc = makeDoc({ status: "parsed", has_issues: true });
    renderWithProviders(<ErrorDocsTab docs={[doc]} />);
    expect(screen.getByText("Проблемы в СФ")).toBeInTheDocument();
  });

  it("renders status=error doc with 'Ошибка парсинга' status", () => {
    renderWithProviders(<ErrorDocsTab docs={[makeDoc()]} />);
    expect(screen.getByText("Ошибка парсинга")).toBeInTheDocument();
  });

  it("opens delete confirmation dialog before deleting", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ErrorDocsTab docs={[makeDoc()]} />);
    await user.click(screen.getByRole("button", { name: /удалить/i }));
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
  });

  it("deletes document after confirmation", async () => {
    const onDelete = vi.fn();
    server.use(
      http.delete("/api/invoices/documents/:id", () => {
        onDelete();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ErrorDocsTab docs={[makeDoc()]} />);
    await user.click(screen.getByRole("button", { name: /удалить/i }));
    await user.click(await screen.findByRole("button", { name: "Удалить" }));
    await waitFor(() => expect(onDelete).toHaveBeenCalledOnce());
  });

  it("calls reparse endpoint on reparse button click", async () => {
    const onReparse = vi.fn();
    server.use(
      http.post("/api/invoices/documents/:id/reparse", ({ params }) => {
        onReparse(params.id);
        return HttpResponse.json(makeDoc({ id: Number(params.id), status: "parsed" }));
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ErrorDocsTab docs={[makeDoc({ id: 1 })]} />);
    await user.click(screen.getByRole("button", { name: /переразобрать/i }));
    await waitFor(() => expect(onReparse).toHaveBeenCalledWith("1"));
  });
});
