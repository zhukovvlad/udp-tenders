import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Routes, Route } from "react-router-dom";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import { sampleReferencePrice, sampleDashboardInvoices } from "@/test/fixtures";
import ProjectPage from "./ProjectPage";

// MSW handlers provide:
//   GET /api/projects        → [sampleProject]  (id=1, name="ЖК Радуга")
//   GET /api/dashboard/*     → sampleDashboardSummary / []
//   GET /api/reference-prices → []
//   GET /api/material-classes → [sampleMaterialClass]

/** Render ProjectPage inside a proper Route so useParams() extracts the id. */
function renderProject(id: string = "1") {
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:id" element={<ProjectPage />} />
    </Routes>,
    { initialRoute: `/projects/${id}` },
  );
}

describe("ProjectPage", () => {
  it("renders project name in header", async () => {
    renderProject();
    await waitFor(() => {
      // Name appears in both breadcrumb and page heading
      expect(screen.getAllByText("ЖК Радуга").length).toBeGreaterThan(0);
    });
  });

  it("renders all four tabs", async () => {
    renderProject();
    await waitFor(() => {
      expect(screen.getByTestId("project-tab-overview")).toBeInTheDocument();
      expect(screen.getByTestId("project-tab-invoices")).toBeInTheDocument();
      expect(screen.getByTestId("project-tab-prices")).toBeInTheDocument();
      expect(screen.getByTestId("project-tab-suppliers")).toBeInTheDocument();
      expect(screen.getByTestId("project-tab-monthly")).toBeInTheDocument();
    });
  });

  it("shows KPI cards after summary loads", async () => {
    renderProject();
    await waitFor(() => {
      expect(screen.getByText("Оборот, ₽ с НДС")).toBeInTheDocument();
      expect(screen.getByText("Счетов")).toBeInTheDocument();
    });
  });

  it("switches to Плановые цены tab", async () => {
    const user = userEvent.setup();
    renderProject();
    const tab = await screen.findByTestId("project-tab-prices");
    await user.click(tab);
    await waitFor(() => {
      expect(screen.getByText(/Плановые цены/)).toBeInTheDocument();
    });
  });

  it("shows empty state for invalid project id", async () => {
    renderProject("abc");
    await waitFor(() => {
      expect(screen.getByText("Объект не найден")).toBeInTheDocument();
    });
  });

  it("clicking configure price button switches to prices tab", async () => {
    server.use(
      http.get("/api/dashboard/calculations", () =>
        HttpResponse.json([
          {
            id: 1,
            project_id: 1,
            material_class_id: 1,
            material_class_name: "В25",
            period_start: "2026-04-01",
            period_end: "2026-04-30",
            total_qty: 10,
            material_total: 80000,
            delivery_total: 0,
            avg_price: 8000,
            invoice_count: 1,
            reference_price: null,
            deviation_pct: null,
            deviation_amount: null,
          },
        ])
      )
    );

    const user = userEvent.setup();
    renderProject();

    const configureBtn = await screen.findByRole("button", { name: /настроить/i });
    await user.click(configureBtn);

    await waitFor(() => {
      expect(screen.getByText("Нет плановых цен")).toBeInTheDocument();
    });
  });

  it("shows edit and delete buttons when reference prices exist", async () => {
    server.use(
      http.get("/api/reference-prices", () =>
        HttpResponse.json([sampleReferencePrice])
      )
    );
    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-prices");
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getByTestId(`rp-edit-${sampleReferencePrice.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`rp-delete-${sampleReferencePrice.id}`)).toBeInTheDocument();
    });
  });

  it("opens edit dialog when pencil button is clicked", async () => {
    server.use(
      http.get("/api/reference-prices", () =>
        HttpResponse.json([sampleReferencePrice])
      )
    );
    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-prices");
    await user.click(tab);

    const editBtn = await screen.findByTestId(`rp-edit-${sampleReferencePrice.id}`);
    await user.click(editBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Редактировать плановую цену")
      ).toBeInTheDocument();
    });
  });

  it("calls delete API when delete confirmed via dialog", async () => {
    let deleteCalled = false;
    server.use(
      http.get("/api/reference-prices", () =>
        HttpResponse.json([sampleReferencePrice])
      ),
      http.delete("/api/reference-prices/:id", () => {
        deleteCalled = true;
        return HttpResponse.json({ message: "Удалено" });
      })
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-prices");
    await user.click(tab);

    const deleteBtn = await screen.findByTestId(`rp-delete-${sampleReferencePrice.id}`);
    await user.click(deleteBtn);

    // Confirmation dialog appears
    const confirmBtn = await screen.findByTestId("rp-delete-confirm");
    await user.click(confirmBtn);

    await waitFor(() => expect(deleteCalled).toBe(true));
  });

  it("shows all three invoice stages in the invoices tab", async () => {
    server.use(
      http.get("/api/dashboard/invoices", () =>
        HttpResponse.json(sampleDashboardInvoices)
      )
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-invoices");
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getByText("Подтверждён")).toBeInTheDocument();
      expect(screen.getByText("Разобрать")).toBeInTheDocument();
      expect(screen.getByText("Ожидает")).toBeInTheDocument();
    });
  });

  it("uses configured confidence threshold for stage classification", async () => {
    // At threshold 0.9, invoice id=203 (ai_confidence=0.88) becomes
    // "Разобрать" instead of "Ожидает", so two invoices show "Разобрать".
    server.use(
      http.get("/api/settings", () =>
        HttpResponse.json({ api_key_set: true, model: "m", confidence_threshold: 0.9 })
      ),
      http.get("/api/dashboard/invoices", () =>
        HttpResponse.json(sampleDashboardInvoices)
      )
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-invoices");
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getAllByText("Разобрать")).toHaveLength(2);
      expect(screen.queryByText("Ожидает")).not.toBeInTheDocument();
    });
  });

  // ── По месяцам tab ──────────────────────────────────────────────────────

  it("renders По месяцам tab and shows month rows", async () => {
    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);

    // Январь и Март присутствуют из фикстуры
    await waitFor(() => {
      expect(screen.getByText(/Январь 2026/)).toBeInTheDocument();
      expect(screen.getByText(/Март 2026/)).toBeInTheDocument();
    });
  });

  it("shows empty month row (Февраль) between data months", async () => {
    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getByText(/Февраль 2026/)).toBeInTheDocument();
    });
  });

  it("shows empty state in По месяцам when no invoices", async () => {
    server.use(
      http.get("/api/dashboard/monthly-summary", () => HttpResponse.json([]))
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);

    await waitFor(() => {
      expect(screen.getByText(/Нет счетов по этому объекту/)).toBeInTheDocument();
    });
  });

  it("clicking a month row navigates to Счета tab with filter applied", async () => {
    server.use(
      http.get("/api/dashboard/invoices", () =>
        HttpResponse.json(sampleDashboardInvoices)
      )
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);

    // Click the Январь row (non-empty)
    const janRow = await screen.findByText(/Январь 2026/);
    await user.click(janRow);

    // Should now be on Счета tab with a month filter badge visible
    await waitFor(() => {
      expect(screen.getByText(/Фильтр: Январь 2026/)).toBeInTheDocument();
    });
  });

  it("month filter reset button clears filter", async () => {
    server.use(
      http.get("/api/dashboard/invoices", () =>
        HttpResponse.json(sampleDashboardInvoices)
      )
    );

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);

    const janRow = await screen.findByText(/Январь 2026/);
    await user.click(janRow);

    const resetBtn = await screen.findByText("Сбросить");
    await user.click(resetBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Фильтр:/)).not.toBeInTheDocument();
    });
  });

  it("CSV export button triggers download with correct filename and BOM content", async () => {
    const user = userEvent.setup();
    renderProject();

    // Navigate to monthly tab before mocking anything (avoids interfering with render)
    const tab = await screen.findByTestId("project-tab-monthly");
    await user.click(tab);
    const exportBtn = await screen.findByRole("button", { name: /Экспорт CSV/i });

    // Set up mocks only after the component has rendered
    const capturedBlobParts: string[] = [];
    const anchorClicks: { download: string }[] = [];
    const origCreateObjectURL = URL.createObjectURL;

    try {
      URL.createObjectURL = (_blob: Blob) => "blob:fake";

      const realBlob = globalThis.Blob;
      const capturedBlobPartsRef = capturedBlobParts;
      class CsvCapturingBlob extends realBlob {
        constructor(parts?: BlobPart[], opts?: BlobPropertyBag) {
          super(parts ?? [], opts);
          if (opts?.type?.includes("csv") && parts) {
            parts.forEach((p) => typeof p === "string" && capturedBlobPartsRef.push(p));
          }
        }
      }
      vi.stubGlobal("Blob", CsvCapturingBlob);

      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === "a") {
          vi.spyOn(el as HTMLAnchorElement, "click").mockImplementation(() => {
            anchorClicks.push({ download: (el as HTMLAnchorElement).download });
          });
        }
        return el;
      });

      await user.click(exportBtn);

      // Filename is correct
      expect(anchorClicks).toHaveLength(1);
      expect(anchorClicks[0].download).toMatch(/закупки-по-месяцам-.*\.csv/);

      // Blob starts with UTF-8 BOM and contains expected semicolon-delimited CSV structure
      expect(capturedBlobParts).toHaveLength(1);
      expect(capturedBlobParts[0].startsWith("\uFEFF")).toBe(true);
      expect(capturedBlobParts[0]).toContain("Период;Оборот (₽);Объём (м³);Счетов");
      expect(capturedBlobParts[0]).toContain("Январь 2026");
      expect(capturedBlobParts[0]).toContain("Март 2026");
    } finally {
      URL.createObjectURL = origCreateObjectURL;
      vi.unstubAllGlobals();
      vi.restoreAllMocks();
    }
  });

  // ── Period filter ───────────────────────────────────────────────────────

  it("period filter inputs send period_start/period_end to calculations API", async () => {
    const receivedParams: URLSearchParams[] = [];
    server.use(
      http.get("/api/dashboard/calculations", ({ request }) => {
        receivedParams.push(new URL(request.url).searchParams);
        return HttpResponse.json([]);
      })
    );

    const user = userEvent.setup();
    renderProject();

    const startInput = await screen.findByTestId("period-start-input");
    const endInput = screen.getByTestId("period-end-input");

    await user.type(startInput, "2025-01-01");
    await user.type(endInput, "2025-03-31");

    // Wait for debounce to fire and a request with both params to arrive
    await waitFor(() => {
      const withBoth = receivedParams.find(
        (p) => p.get("period_start") === "2025-01-01" && p.get("period_end") === "2025-03-31"
      );
      expect(withBoth).toBeDefined();
    }, { timeout: 2000 });
  });

  it("period reset button clears inputs and removes period params from calculations API", async () => {
    const sampleCalc = {
      material_class_id: 1,
      material_class_name: "В%25",
      period_start: "2025-01-01",
      period_end: "2025-01-31",
      total_qty: 10,
      material_total: 80000,
      delivery_total: 0,
      avg_price: 8000,
      invoice_count: 1,
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
    };
    const receivedParams: URLSearchParams[] = [];
    server.use(
      http.get("/api/dashboard/calculations", ({ request }) => {
        receivedParams.push(new URL(request.url).searchParams);
        return HttpResponse.json([sampleCalc]);
      })
    );

    const user = userEvent.setup();
    renderProject();

    const startInput = await screen.findByTestId("period-start-input");
    const endInput = screen.getByTestId("period-end-input");

    await user.type(startInput, "2025-01-01");
    await user.type(endInput, "2025-03-31");

    await waitFor(() => {
      expect(receivedParams.some((p) => p.get("period_start") === "2025-01-01")).toBe(true);
    }, { timeout: 2000 });

    receivedParams.length = 0;

    const resetBtn = screen.getByTestId("period-reset-button");
    await user.click(resetBtn);

    await waitFor(() => {
      const withoutPeriod = receivedParams.find(
        (p) => !p.get("period_start") && !p.get("period_end")
      );
      expect(withoutPeriod).toBeDefined();
    }, { timeout: 2000 });

    expect((startInput as HTMLInputElement).value).toBe("");
    expect((endInput as HTMLInputElement).value).toBe("");
  });
});
