import { describe, it, expect } from "vitest";
import { waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import ReferencePrices from "./ReferencePrices";

describe("ReferencePrices", () => {
  it("renders without errors", async () => {
    renderWithProviders(<ReferencePrices />);
    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });
});
