import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
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
});
