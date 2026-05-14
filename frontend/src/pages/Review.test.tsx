import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import { sampleDocument } from "@/test/fixtures";
import Review from "./Review";

// Review использует useParams<{ id: string }>(). MemoryRouter без определённого
// <Route path="/documents/:id"> не разрезает path и useParams возвращает {}.
// Проще всего для теста замокать useParams напрямую.
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  );
  return {
    ...actual,
    useParams: () => ({ id: "10" }),
  };
});

describe("ReviewPage", () => {
  it("renders document data after fetching", async () => {
    renderWithProviders(<Review />);
    // Используем getAllByText: PageHeader (title+subtitle) и Breadcrumbs
    // дублируют номер СФ — это by design страницы.
    await waitFor(() => {
      expect(screen.getAllByText(/СФ-101/).length).toBeGreaterThan(0);
    });
  });

  it("displays the supplier name", async () => {
    renderWithProviders(<Review />);
    await waitFor(() => {
      expect(screen.getAllByText(/ООО Поставщик/).length).toBeGreaterThan(0);
    });
  });

  it("displays at least one item from invoice", async () => {
    renderWithProviders(<Review />);
    // raw_name рендерится как value <input>, не текстовый узел —
    // getByText его не найдёт, нужен getByDisplayValue.
    await waitFor(() => {
      expect(screen.getByDisplayValue(/Бетон В25/)).toBeInTheDocument();
    });
  });

  it("shows Подтвердить button when invoice is not verified", async () => {
    renderWithProviders(<Review />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Подтвердить/i })).toBeInTheDocument();
    });
  });

  it("clicking Подтвердить calls POST /api/invoices/100/verify", async () => {
    // Используем дефолтный stateful handler: после мутации GET /documents/:id
    // вернёт verified: true, что подтверждает корректную инвалидацию кэша.
    const user = userEvent.setup();
    renderWithProviders(<Review />);

    const btn = await screen.findByRole("button", { name: /Подтвердить/i });
    await user.click(btn);

    // После рефетча UI переключается на «Снять подтверждение».
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Снять подтверждение/i })).toBeInTheDocument();
    });
  });

  it("shows Снять подтверждение button when invoice is verified", async () => {
    const verifiedDoc = {
      ...sampleDocument,
      invoices: [{ ...sampleDocument.invoices[0], verified: true, verified_at: "2026-05-14T12:00:00" }],
    };
    server.use(
      http.get("/api/invoices/documents/:id", () => HttpResponse.json(verifiedDoc))
    );

    renderWithProviders(<Review />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Снять подтверждение/i })).toBeInTheDocument();
    });
  });

  it("clicking Снять подтверждение calls POST /api/invoices/100/unverify", async () => {
    let unverifyCalled = false;
    const verifiedDoc = {
      ...sampleDocument,
      invoices: [{ ...sampleDocument.invoices[0], verified: true, verified_at: "2026-05-14T12:00:00" }],
    };
    server.use(
      http.get("/api/invoices/documents/:id", () => HttpResponse.json(verifiedDoc)),
      http.post("/api/invoices/:id/unverify", ({ params }) => {
        if (params.id === "100") unverifyCalled = true;
        return HttpResponse.json({ message: "Отметка снята", invoice_id: 100 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<Review />);

    const btn = await screen.findByRole("button", { name: /Снять подтверждение/i });
    await user.click(btn);

    await waitFor(() => expect(unverifyCalled).toBe(true));
  });

  it("Подтвердить button is disabled when there are unsaved changes (dirty)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Review />);

    // Switch to header tab to expose editable fields
    const headerTab = await screen.findByRole("button", { name: /Шапка/i });
    await user.click(headerTab);

    // Edit the invoice number to make the form dirty
    const numberInput = await screen.findByDisplayValue("СФ-101");
    await user.clear(numberInput);
    await user.type(numberInput, "СФ-999");

    await waitFor(() => {
      const verifyBtn = screen.getByRole("button", { name: /Подтвердить/i });
      expect(verifyBtn).toBeDisabled();
    });
  });
});
