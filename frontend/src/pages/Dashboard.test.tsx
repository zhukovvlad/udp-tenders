import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import Dashboard from "./Dashboard";

describe("Dashboard", () => {
  it("renders portfolio header", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Сводка по портфелю/)).toBeInTheDocument();
    });
  });

  it("renders KPI cards", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Переплата к плановым/)).toBeInTheDocument();
      expect(screen.getByText(/Требуют внимания/)).toBeInTheDocument();
    });
  });

  it("renders price dynamics section", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Динамика цен на ключевые материалы/)).toBeInTheDocument();
    });
  });

  it("renders projects list", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Объекты/)).toBeInTheDocument();
    });
  });
});
