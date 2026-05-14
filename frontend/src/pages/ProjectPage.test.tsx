import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Routes, Route } from "react-router-dom";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import { sampleReferencePrice } from "@/test/fixtures";
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
    });
  });

  it("shows KPI cards after summary loads", async () => {
    renderProject();
    await waitFor(() => {
      expect(screen.getByText("Оборот")).toBeInTheDocument();
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
      expect(screen.getByLabelText("Редактировать")).toBeInTheDocument();
      expect(screen.getByLabelText("Удалить")).toBeInTheDocument();
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

    const editBtn = await screen.findByLabelText("Редактировать");
    await user.click(editBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Редактировать плановую цену")
      ).toBeInTheDocument();
    });
  });

  it("calls delete API when delete confirmed", async () => {
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
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const user = userEvent.setup();
    renderProject();

    const tab = await screen.findByTestId("project-tab-prices");
    await user.click(tab);

    const deleteBtn = await screen.findByLabelText("Удалить");
    await user.click(deleteBtn);

    await waitFor(() => expect(deleteCalled).toBe(true));

    vi.restoreAllMocks();
  });
});
