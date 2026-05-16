// Tests for SingleRunTab component (Phase 10-E-1)
// Verifies skeleton / complete / error states and Command Palette entry registration

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: () => null }),
}));

// Mock toast
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
const mockToastInfo = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
    info: mockToastInfo,
    dismiss: vi.fn(),
  }),
}));

// Mock useCommandPaletteEntry to capture registered entries
const registeredEntries: Array<{ id: string; label: string }> = [];
vi.mock("@/hooks/use-command-palette", () => ({
  useCommandPaletteEntry: (entry: { id: string; label: string }) => {
    // Capture registration calls
    registeredEntries.push(entry);
  },
}));

// Mock useBacktestJob
const mockStart = vi.fn();
const mockCancel = vi.fn();
const mockReset = vi.fn();

let mockJobStatus: "idle" | "running" | "complete" | "error" | "cancelled" = "idle";
let mockJobResult: unknown = null;
let mockJobError: { code: string; message: string } | null = null;
let mockJobProgress: { phase?: string } | null = null;

vi.mock("@/hooks/use-backtest-job", () => ({
  useBacktestJob: () => ({
    status: mockJobStatus,
    progress: mockJobProgress,
    result: mockJobResult,
    error: mockJobError,
    start: mockStart,
    cancel: mockCancel,
    reset: mockReset,
  }),
}));

// Mock SWR for StrategyPresetSelect
vi.mock("swr", () => ({
  default: () => ({
    data: [{ name: "MA20_MA60", type: "moving_average_cross", params: {} }],
    isLoading: false,
  }),
}));

// Mock heavy external dependencies (lightweight-charts doesn't work in jsdom)
vi.mock("@/components/backtest/CandleChartWithMarkers", () => ({
  CandleChartWithMarkers: () => <div data-testid="candle-chart-with-markers" />,
}));

vi.mock("@/components/backtest/EquityCurveChart", () => ({
  EquityCurveChart: () => <div data-testid="equity-curve-chart" />,
}));

// Mock StockSelector and MarketSwitcher (avoid full rendering)
vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ onChange }: { value: string; onChange: (m: string) => void }) => (
    <button type="button" onClick={() => onChange("tw")} data-testid="market-switcher">
      TW
    </button>
  ),
}));

vi.mock("@/components/stock-selector", () => ({
  StockSelector: ({ onChange }: { onChange: (v: string) => void }) => (
    <input
      data-testid="stock-selector"
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

import { SingleRunTab } from "@/components/backtest/SingleRunTab";

describe("SingleRunTab", () => {
  beforeEach(() => {
    mockJobStatus = "idle";
    mockJobResult = null;
    mockJobError = null;
    mockJobProgress = null;
    registeredEntries.length = 0;
    mockStart.mockClear();
    mockCancel.mockClear();
    mockReset.mockClear();
  });

  it("renders form in idle state", () => {
    render(<SingleRunTab />);
    expect(screen.getByTestId("start-backtest-btn")).toBeInTheDocument();
    expect(screen.getByText("設定參數後按「開始回測」")).toBeInTheDocument();
  });

  it("renders CardSkeleton × 5 + ChartSkeleton × 2 + TableSkeleton when running", () => {
    mockJobStatus = "running";
    mockJobProgress = { phase: "loading_data" };
    render(<SingleRunTab />);
    expect(screen.getAllByTestId("card-skeleton")).toHaveLength(5);
    expect(screen.getAllByTestId("chart-skeleton")).toHaveLength(2);
    expect(screen.getByTestId("table-skeleton")).toBeInTheDocument();
  });

  it("renders result components when complete", () => {
    mockJobStatus = "complete";
    mockJobResult = {
      symbol: "2330",
      market: "tw",
      currency: "TWD",
      engine: "vectorized",
      strategy_type: "moving_average_cross",
      strategy_params: { short_window: 20, long_window: 60 },
      metrics: {
        total_trades: 5,
        total_return: 0.2,
        annual_return: 0.05,
        max_drawdown: -0.1,
        sharpe_ratio: 0.8,
      },
      equity_curve: [{ date: "2020-01-02", value: 1000000 }],
      trades: [
        {
          entry_date: "2020-03-15",
          exit_date: "2020-05-20",
          side: "long",
          entry_price: 280,
          exit_price: 310,
          shares: 1000,
          pnl: 30000,
          return_pct: 0.107,
        },
      ],
      signals: [{ date: "2020-03-15", side: "buy", price: 280 }],
      price_data: [{ date: "2020-01-02", open: 330, high: 335, low: 328, close: 333, volume: 10000 }],
      dca_warning: null,
    };
    render(<SingleRunTab />);
    expect(screen.getByTestId("tearsheet-cards")).toBeInTheDocument();
    expect(screen.getByTestId("trades-table")).toBeInTheDocument();
    expect(screen.getByTestId("equity-curve-chart")).toBeInTheDocument();
  });

  it("renders error panel when status=error", () => {
    mockJobStatus = "error";
    mockJobError = { code: "NO_DATA", message: "無資料" };
    render(<SingleRunTab />);
    expect(screen.getByText("執行失敗")).toBeInTheDocument();
    expect(screen.getByText(/無資料/)).toBeInTheDocument();
  });

  it("registers 4 Command Palette entries", () => {
    render(<SingleRunTab />);
    const ids = registeredEntries.map((e) => e.id);
    expect(ids).toContain("bt-single");
    expect(ids).toContain("bt-batch");
    expect(ids).toContain("bt-sweep");
    expect(ids).toContain("bt-wfa");
  });
});
