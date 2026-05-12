import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import UploadPage from "./Upload";

describe("UploadPage", () => {
  it("renders page header", async () => {
    renderWithProviders(<UploadPage />);
    await waitFor(() => {
      expect(screen.getByText(/Загрузка документов/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no project selected yet", async () => {
    renderWithProviders(<UploadPage />);
    // Без выбранного проекта Dropzone скрыт, показан EmptyState.
    await waitFor(() => {
      expect(screen.getByText(/Сначала выберите объект/)).toBeInTheDocument();
    });
  });

  it("renders project selector with placeholder", async () => {
    renderWithProviders(<UploadPage />);
    await waitFor(() => {
      // EntitySelect placeholder "Выберите объект"
      expect(screen.getByText(/Выберите объект/)).toBeInTheDocument();
    });
  });
});
