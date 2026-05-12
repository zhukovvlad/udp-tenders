import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import Dashboard from "./Dashboard";

describe("Dashboard", () => {
  it("renders page header", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Аналитика/)).toBeInTheDocument();
    });
  });

  it("renders project selector", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      // KPI рендерятся только после выбора проекта; без выбора виден placeholder.
      expect(screen.getByText(/Выберите объект/)).toBeInTheDocument();
    });
  });
});
