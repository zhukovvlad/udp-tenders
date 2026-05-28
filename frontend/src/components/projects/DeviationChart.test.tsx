import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/utils";
import type { DashboardCalculation } from "@/types/dashboard";

import { DeviationChart } from "./DeviationChart";

/**
 * Фабрика строки DashboardCalculation для тестов.
 * reference_price !== null → покрытый месяц; null → непокрытый.
 */
function makeCalc(
  overrides: Partial<DashboardCalculation> & { material_class_id: number; material_class_name: string }
): DashboardCalculation {
  return {
    period_start: "2024-01-01",
    period_end: "2024-01-31",
    avg_price: 6000,
    reference_price: 5500,
    deviation_pct: ((6000 - 5500) / 5500) * 100,
    deviation_amount: 500 * 100,
    material_total: 500000,
    delivery_total: 50000,
    total_qty: 100,
    invoice_count: 3,
    ...overrides,
  };
}

// Ищем элементы по SVG axis tick (tspan внутри YAxis) — recharts дублирует текст
// в служебном span измерений. Используем getAllByText и берём первый реальный элемент.
function findAxisLabel(name: string) {
  return screen.getAllByText(name)[0];
}

// ─── 1. Полное покрытие ───────────────────────────────────────────────────────

describe("Полное покрытие (все месяцы с базовой ценой)", () => {
  it("класс присутствует на графике, data-partial-coverage отсутствует, в баннере нет", () => {
    const jan = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: 5500,
      total_qty: 60,
      deviation_amount: 500 * 60,
    });
    const feb = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-02-01",
      period_end: "2024-02-29",
      reference_price: 5500,
      total_qty: 40,
      deviation_amount: 500 * 40,
    });

    renderWithProviders(
      <DeviationChart calculations={[jan, feb]} periodFilterActive />,
    );

    expect(findAxisLabel("B25")).toBeInTheDocument();
    expect(document.querySelector("[data-partial-coverage='true']")).not.toBeInTheDocument();
    expect(screen.queryByText(/без базовой цены/i)).not.toBeInTheDocument();
  });
});

// ─── 2. Частичное покрытие ──────────────────────────────────────────────────

describe("Частичное покрытие (хотя бы один месяц покрыт)", () => {
  it("класс на графике, data-partial-coverage=true, в баннере отсутствует", () => {
    const covered = makeCalc({
      material_class_id: 2,
      material_class_name: "B15",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: 5490,
      total_qty: 80,
      avg_price: 6000,
      deviation_pct: ((6000 - 5490) / 5490) * 100,
      deviation_amount: (6000 - 5490) * 80,
    });
    const uncovered = makeCalc({
      material_class_id: 2,
      material_class_name: "B15",
      period_start: "2023-12-01",
      period_end: "2023-12-31",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 20,
    });

    renderWithProviders(
      <DeviationChart calculations={[uncovered, covered]} periodFilterActive />,
    );

    // Класс на графике
    expect(findAxisLabel("B15")).toBeInTheDocument();
    // В баннере отсутствует
    expect(screen.queryByText(/без базовой цены/i)).not.toBeInTheDocument();
    // Бар помечен как частично покрытый
    expect(document.querySelector("[data-partial-coverage='true']")).toBeInTheDocument();
  });

  it("deviation_pct считается только по покрытым месяцам", () => {
    const covered = makeCalc({
      material_class_id: 3,
      material_class_name: "B30",
      period_start: "2024-02-01",
      period_end: "2024-02-29",
      reference_price: 5000,
      total_qty: 50,
      avg_price: 6000,
      deviation_pct: 20,
      deviation_amount: 50000,
    });
    const uncovered = makeCalc({
      material_class_id: 3,
      material_class_name: "B30",
      period_start: "2023-12-01",
      period_end: "2023-12-31",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 30,
    });

    renderWithProviders(
      <DeviationChart calculations={[covered, uncovered]} periodFilterActive />,
    );

    // Класс виден на графике → deviation_pct не null (рассчитан только по покрытым)
    expect(findAxisLabel("B30")).toBeInTheDocument();
    expect(screen.queryByText(/без базовой цены/i)).not.toBeInTheDocument();
  });
});

// ─── 3. Нулевое покрытие ─────────────────────────────────────────────────────

describe("Нулевое покрытие (все месяцы без базовой цены)", () => {
  it("класс в баннере, на графике отсутствует, data-partial-coverage нет", () => {
    const uncov1 = makeCalc({
      material_class_id: 4,
      material_class_name: "B35",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 50,
    });
    const uncov2 = makeCalc({
      material_class_id: 4,
      material_class_name: "B35",
      period_start: "2024-02-01",
      period_end: "2024-02-29",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 30,
    });

    renderWithProviders(
      <DeviationChart calculations={[uncov1, uncov2]} periodFilterActive />,
    );

    // Баннер «без базовой цены» отображается с именем класса
    expect(screen.getByText(/без базовой цены/i)).toBeInTheDocument();
    // data-partial-coverage не устанавливается при нулевом покрытии
    expect(document.querySelector("[data-partial-coverage='true']")).not.toBeInTheDocument();
  });
});

// ─── 4. Смешанный набор ───────────────────────────────────────────────────────

describe("Смешанный набор: полный + частичный + нулевой", () => {
  it("каждый класс попадает в правильный блок", () => {
    // B25 — полное покрытие
    const b25jan = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: 5500,
      total_qty: 100,
      deviation_pct: 9.09,
      deviation_amount: 50000,
    });
    const b25feb = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-02-01",
      period_end: "2024-02-29",
      reference_price: 5500,
      total_qty: 100,
      deviation_pct: 9.09,
      deviation_amount: 50000,
    });

    // B15 — частичное покрытие
    const b15jan = makeCalc({
      material_class_id: 2,
      material_class_name: "B15",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: 5490,
      total_qty: 80,
      deviation_pct: 9.29,
      deviation_amount: 40800,
    });
    const b15dec = makeCalc({
      material_class_id: 2,
      material_class_name: "B15",
      period_start: "2023-12-01",
      period_end: "2023-12-31",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 20,
    });

    // B35 — нулевое покрытие
    const b35 = makeCalc({
      material_class_id: 3,
      material_class_name: "B35",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: null,
      deviation_pct: null,
      deviation_amount: null,
      total_qty: 40,
    });

    renderWithProviders(
      <DeviationChart
        calculations={[b25jan, b25feb, b15jan, b15dec, b35]}
        periodFilterActive
      />,
    );

    // B25 и B15 на графике
    expect(findAxisLabel("B25")).toBeInTheDocument();
    expect(findAxisLabel("B15")).toBeInTheDocument();

    // B35 в баннере
    expect(screen.getByText(/без базовой цены/i)).toBeInTheDocument();

    // Только B15 имеет частичное покрытие → ровно один элемент с атрибутом
    const partialCells = document.querySelectorAll("[data-partial-coverage='true']");
    expect(partialCells).toHaveLength(1);
  });
});

// ─── 5. periodFilterActive=false — регрессия ─────────────────────────────────

describe("periodFilterActive=false (latest-month режим)", () => {
  it("показывает только последний месяц, data-partial-coverage не выставляется", () => {
    const jan = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-01-01",
      period_end: "2024-01-31",
      reference_price: 5000,
      total_qty: 50,
    });
    const feb = makeCalc({
      material_class_id: 1,
      material_class_name: "B25",
      period_start: "2024-02-01",
      period_end: "2024-02-29",
      reference_price: 5000,
      total_qty: 70,
    });

    renderWithProviders(
      <DeviationChart calculations={[jan, feb]} periodFilterActive={false} />,
    );

    expect(findAxisLabel("B25")).toBeInTheDocument();
    // В latest-month режиме covered_qty всегда null → нет data-partial-coverage
    expect(document.querySelector("[data-partial-coverage='true']")).not.toBeInTheDocument();
  });
});

