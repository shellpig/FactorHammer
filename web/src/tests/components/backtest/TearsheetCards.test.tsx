// Tests for TearsheetCards component (Phase 10-E-1)

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TearsheetCards } from "@/components/backtest/TearsheetCards";

const BASE_METRICS = {
  total_trades: 15,
  total_return: 0.345,
  annual_return: 0.0876,
  max_drawdown: -0.182,
  sharpe_ratio: 0.92,
};

describe("TearsheetCards", () => {
  it("renders 5 cards", () => {
    render(<TearsheetCards metrics={BASE_METRICS} currency="TWD" />);
    const cards = screen.getByTestId("tearsheet-cards");
    expect(cards).toBeInTheDocument();
    const values = screen.getAllByTestId("metric-value");
    expect(values).toHaveLength(5);
  });

  it("displays total trades as integer", () => {
    render(<TearsheetCards metrics={BASE_METRICS} currency="TWD" />);
    expect(screen.getByText("15")).toBeInTheDocument();
  });

  it("formats total return as percentage", () => {
    render(<TearsheetCards metrics={BASE_METRICS} currency="TWD" />);
    expect(screen.getByText("34.50%")).toBeInTheDocument();
  });

  it("shows positive return in green class", () => {
    render(<TearsheetCards metrics={{ ...BASE_METRICS, total_return: 0.1 }} currency="TWD" />);
    // find the total return value element
    const values = screen.getAllByTestId("metric-value");
    const returnVal = values.find((el) => el.textContent === "10.00%");
    expect(returnVal).toBeDefined();
    expect(returnVal!.className).toContain("emerald");
  });

  it("shows negative return in red class", () => {
    render(<TearsheetCards metrics={{ ...BASE_METRICS, total_return: -0.05 }} currency="TWD" />);
    const values = screen.getAllByTestId("metric-value");
    const returnVal = values.find((el) => el.textContent === "-5.00%");
    expect(returnVal).toBeDefined();
    expect(returnVal!.className).toContain("rose");
  });

  it("shows max drawdown always in red class", () => {
    render(<TearsheetCards metrics={{ ...BASE_METRICS, max_drawdown: -0.1 }} currency="TWD" />);
    const values = screen.getAllByTestId("metric-value");
    const ddVal = values.find((el) => el.textContent === "-10.00%");
    expect(ddVal).toBeDefined();
    expect(ddVal!.className).toContain("rose");
  });

  it("shows 定期定額不適用 for DCA mode", () => {
    render(<TearsheetCards metrics={{ ...BASE_METRICS, total_trades: null }} currency="TWD" isDca />);
    expect(screen.getByText("定期定額不適用")).toBeInTheDocument();
  });

  it("displays currency label TWD", () => {
    render(<TearsheetCards metrics={BASE_METRICS} currency="TWD" />);
    // Each card shows currency label — check at least one
    const labels = screen.getAllByText("幣別：TWD");
    expect(labels.length).toBeGreaterThanOrEqual(1);
  });

  it("displays currency label USD", () => {
    render(<TearsheetCards metrics={BASE_METRICS} currency="USD" />);
    const labels = screen.getAllByText("幣別：USD");
    expect(labels.length).toBeGreaterThanOrEqual(1);
  });

  it("shows null sharpe as —", () => {
    render(<TearsheetCards metrics={{ ...BASE_METRICS, sharpe_ratio: null }} currency="TWD" />);
    const values = screen.getAllByTestId("metric-value");
    const sharpeVal = values[4]; // last card
    expect(sharpeVal.textContent).toBe("—");
  });
});
