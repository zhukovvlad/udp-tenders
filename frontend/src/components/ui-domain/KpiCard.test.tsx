import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "./KpiCard";

it("renders multi-value rows (name left, value right) instead of single value", () => {
  render(
    <KpiCard
      label="Объёмы"
      values={[
        { label: "Бетон", value: "5 677,5 м³" },
        { label: "Арматура", value: "124,8 т" },
      ]}
    />,
  );
  expect(screen.getByText("5 677,5 м³")).toBeInTheDocument();
  expect(screen.getByText("Арматура")).toBeInTheDocument();
});
