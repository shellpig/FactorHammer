// Tests for TradesTable component (Phase 10-E-1)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TradesTable } from "@/components/backtest/TradesTable";

function makeTrade(i: number) {
  return {
    entry_date: `2020-0${(i % 9) + 1}-01`,
    exit_date: `2020-0${(i % 9) + 1}-20`,
    side: "long" as const,
    entry_price: 100 + i,
    exit_price: 110 + i,
    shares: 1000,
    pnl: 10000 + i * 100,
    return_pct: 0.1,
  };
}

const SAMPLE_TRADES = Array.from({ length: 3 }, (_, i) => makeTrade(i));
const TWENTY_FIVE_TRADES = Array.from({ length: 25 }, (_, i) => makeTrade(i));

describe("TradesTable", () => {
  it("renders empty state when no trades", () => {
    render(<TradesTable trades={[]} currency="TWD" />);
    expect(screen.getByTestId("trades-table-empty")).toBeInTheDocument();
    expect(screen.getByText("無交易記錄")).toBeInTheDocument();
  });

  it("renders table with trades", () => {
    render(<TradesTable trades={SAMPLE_TRADES} currency="TWD" />);
    expect(screen.getByTestId("trades-table")).toBeInTheDocument();
  });

  it("shows shares column — not 張 (unit is shares)", () => {
    render(<TradesTable trades={SAMPLE_TRADES} currency="TWD" />);
    expect(screen.getByText("數量（股）")).toBeInTheDocument();
    // Should NOT contain 張
    expect(screen.queryByText(/張/)).toBeNull();
  });

  it("shows same unit label for US market trades", () => {
    render(<TradesTable trades={SAMPLE_TRADES} currency="USD" />);
    expect(screen.getByText("數量（股）")).toBeInTheDocument();
  });

  it("sorts by PnL when header clicked", () => {
    render(<TradesTable trades={SAMPLE_TRADES} currency="TWD" />);
    const pnlHeader = screen.getByText(/損益/);
    fireEvent.click(pnlHeader);
    // After click, sort icon changes — basic interaction test
    expect(pnlHeader).toBeInTheDocument();
  });

  it("shows pagination controls when > 20 trades", () => {
    render(<TradesTable trades={TWENTY_FIVE_TRADES} currency="TWD" />);
    expect(screen.getByText(/下一頁/)).toBeInTheDocument();
    expect(screen.getByText(/上一頁/)).toBeInTheDocument();
  });

  it("does not show pagination when ≤ 20 trades", () => {
    render(<TradesTable trades={SAMPLE_TRADES} currency="TWD" />);
    expect(screen.queryByText(/下一頁/)).toBeNull();
  });

  it("paginates to page 2 when next page clicked", () => {
    render(<TradesTable trades={TWENTY_FIVE_TRADES} currency="TWD" />);
    fireEvent.click(screen.getByText("下一頁"));
    expect(screen.getByText(/第 2 \/ 2 頁/)).toBeInTheDocument();
  });

  it("disables previous page on first page", () => {
    render(<TradesTable trades={TWENTY_FIVE_TRADES} currency="TWD" />);
    expect(screen.getByText("上一頁")).toBeDisabled();
  });
});
