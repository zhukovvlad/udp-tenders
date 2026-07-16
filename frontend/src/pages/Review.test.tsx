import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import { setHandlerVerified } from "@/test/handlers";
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
    server.use(
      http.get("/api/invoices/documents/:id", () => HttpResponse.json({
        ...sampleDocument,
        invoices: [{ ...sampleDocument.invoices[0], verified: true, verified_at: "2026-05-14T12:00:00" }],
      }))
    );

    renderWithProviders(<Review />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Снять подтверждение/i })).toBeInTheDocument();
    });
  });

  it("clicking Снять подтверждение calls POST /api/invoices/100/unverify", async () => {
    // Устанавливаем stateful состояние verified=true. После мутации unverify
    // дефолтный handler сбрасывает флаг и рефетч возвращает verified=false.
    setHandlerVerified(100, true);

    const user = userEvent.setup();
    renderWithProviders(<Review />);

    const btn = await screen.findByRole("button", { name: /Снять подтверждение/i });
    await user.click(btn);

    // После рефетча UI переключается на «Подтвердить».
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Подтвердить/i })).toBeInTheDocument();
    });
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

  it("fields are locked and save is disabled when invoice is verified", async () => {
    setHandlerVerified(100, true);

    const user = userEvent.setup();
    renderWithProviders(<Review />);

    // Header inputs locked
    const headerTab = await screen.findByRole("button", { name: /Шапка/i });
    await user.click(headerTab);
    await waitFor(() => {
      expect(screen.getByDisplayValue("СФ-101")).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: /Сохранить/i })).toBeDisabled();

    // Items tab: all item inputs locked (raw_name input)
    const itemsTab = screen.getByRole("button", { name: /Позиции/i });
    await user.click(itemsTab);
    await waitFor(() => {
      expect(screen.getByDisplayValue(/Бетон В25/)).toBeDisabled();
    });

    // Reparse button disabled (exact-match, чтобы не зацепить "Выпрямить и переразобрать")
    expect(screen.getByRole("button", { name: /^Переразобрать$/i })).toBeDisabled();
    // Deskew button присутствует и тоже заблокирован при locked
    expect(screen.getByRole("button", { name: /Выпрямить и переразобрать/i })).toBeDisabled();
  });

  it("delete button is disabled when invoice is verified", async () => {
    setHandlerVerified(100, true);
    renderWithProviders(<Review />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^Удалить$/i })).toBeDisabled();
    });
  });

  it("shows confidence issue on Проблемы tab when threshold is above ai_confidence", async () => {
    // sampleDocument.invoices[0].ai_confidence = 0.92; setting threshold to 0.95 triggers the issue
    server.use(
      http.get("/api/settings", () =>
        HttpResponse.json({ api_key_set: true, model: "m", confidence_threshold: 0.95 })
      )
    );

    const user = userEvent.setup();
    renderWithProviders(<Review />);

    const issuesTab = await screen.findByRole("button", { name: /Проблемы/i });
    await user.click(issuesTab);

    await waitFor(() => {
      expect(screen.getByText(/Низкая уверенность/i)).toBeInTheDocument();
    });
  });

  it("shows «ИИ-разбор: $0.00» when a parse happened but cost is 0 (parse_count > 0)", async () => {
    // Регресс: разбор состоялся (parse_count=1), но OpenRouter не вернул usage.cost
    // (стоимость 0). Гейт parse_count > 0 (а не parse_cost_usd > 0) обязан показать метрику.
    server.use(
      http.get("/api/invoices/documents/:id", () =>
        HttpResponse.json({ ...sampleDocument, parse_cost_usd: 0, parse_count: 1 })
      )
    );

    renderWithProviders(<Review />);

    const costLabel = await screen.findByText(/ИИ-разбор:/);
    expect(costLabel).toHaveTextContent(/ИИ-разбор:\s*\$0\.00/);
  });
});

describe("Review — save warnings", () => {
  it("shows the unknown-unit warning returned by the save call", async () => {
    const user = userEvent.setup();
    server.use(
      http.put("/api/invoices/:id", () =>
        HttpResponse.json({
          message: "Сохранено",
          invoice_id: 100,
          warnings: [{
            field: "raw_unit", code: "unknown_unit",
            message: "Единица измерения «бухта» не найдена в справочнике",
          }],
        }),
      ),
    );

    renderWithProviders(<Review />);

    // Items tab is the default. Edit a unit to make the form dirty (enables Save).
    const unitInput = (await screen.findAllByDisplayValue("м3"))[0];
    await user.clear(unitInput);
    await user.type(unitInput, "бухта");

    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText(/не найдена в справочнике/)).toBeInTheDocument();
  });

  it("clears the warning after a subsequent clean save", async () => {
    const user = userEvent.setup();

    // First save returns a warning
    server.use(
      http.put("/api/invoices/:id", () =>
        HttpResponse.json({
          message: "Сохранено",
          invoice_id: 100,
          warnings: [{
            field: "raw_unit", code: "unknown_unit",
            message: "Единица измерения «бухта» не найдена в справочнике",
          }],
        }),
      ),
    );

    renderWithProviders(<Review />);

    const unitInput = (await screen.findAllByDisplayValue("м3"))[0];
    await user.clear(unitInput);
    await user.type(unitInput, "бухта");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    // Warning appears
    expect(await screen.findByText(/не найдена в справочнике/)).toBeInTheDocument();

    // Override handler to return no warnings on the next save
    server.use(
      http.put("/api/invoices/:id", () =>
        HttpResponse.json({
          message: "Сохранено",
          invoice_id: 100,
          warnings: [],
        }),
      ),
    );

    // After first save overrides are cleared → input reverts to server value "м3".
    // Make the form dirty again by editing that input, then save.
    const unitInput2 = (await screen.findAllByDisplayValue("м3"))[0];
    await user.clear(unitInput2);
    await user.type(unitInput2, "шт");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    // Warning disappears
    await waitFor(() => {
      expect(screen.queryByText(/не найдена в справочнике/)).toBeNull();
    });
  });
});
