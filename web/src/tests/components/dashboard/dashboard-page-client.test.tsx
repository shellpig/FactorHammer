import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";
import type { DashboardPayloadResponse, OhlcvBar } from "@/types/analysis";
import type { Market } from "@/types/market";

// ── Module-level mocks ────────────────────────────────────────────────────────

const apiGetMock = vi.fn();
const mutateMock = vi.fn();
const useDashboardImpl = vi.fn();
const mutateGlobalMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

vi.mock("swr", async (importOriginal) => {
  const actual = await importOriginal<typeof import("swr")>();
  return { ...actual, mutate: (...args: unknown[]) => mutateGlobalMock(...args) };
});

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, apiGet: (...args: unknown[]) => apiGetMock(...args) };
});

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: (...args: unknown[]) => useDashboardImpl(...args),
}));

vi.mock("@/lib/hooks/useP11Valuation", () => ({ useP11Valuation: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11MonthlyRevenue", () => ({ useP11MonthlyRevenue: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11DividendHistory", () => ({ useP11DividendHistory: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11IndustryPer", () => ({ useP11IndustryPer: () => ({ data: undefined, isLoading: false }) }));
vi.mock("@/lib/hooks/useP11InstitutionalCost", () => ({ useP11InstitutionalCost: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11EventCalendar", () => ({ useP11EventCalendar: () => ({ data: undefined, mutate: vi.fn() }) }));

vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ onChange }: { onChange: (m: Market) => void }) => (
    <button type="button" onClick={() => onChange("tw")}>TW</button>
  ),
}));

vi.mock("@/components/stock-selector", () => ({
  StockSelector: ({
    value,
    onChange,
    onInputChange,
  }: {
    value: string;
    onChange: (v: string) => void;
    onInputChange: (v: string) => void;
  }) => (
    <input
      data-testid="stock-selector-input"
      aria-label="stock-input"
      value={value}
      onChange={(e) => onInputChange(e.target.value)}
      onKeyDown={(e) => { if (e.key === "Enter") onChange(value); }}
    />
  ),
}));

vi.mock("@/components/dashboard/candlestick-chart", () => ({
  CandlestickChart: () => <div data-testid="candlestick-chart" />,
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildBar(symbol: string): OhlcvBar {
  return { date: "2026-05-15T00:00:00+08:00", open: 100, high: 110, low: 95, close: 108, volume: 1000000, symbol };
}

function buildPayload(symbol: string, intradayBars: OhlcvBar[] = []): DashboardPayloadResponse {
  return {
    symbol,
    market: "tw",
    subject_name: "Test",
    analysis_time: "2026-05-16 10:00:00",
    ai_enabled: false,
    daily_df: [buildBar(symbol)],
    technical: {
      trend_direction: "up", ma_status: "up", kd_status: "bull", macd_status: "bull",
      volume_status: "normal", volume_price_relation: "up", short_term_score: 0.7,
      short_term_label: "bull",
      short_term_components: { ma: 0.7, kd: 0.7, volume_price: 0.7, breakout: 0.7 },
      resistance_levels: [], support_levels: [], volume_price_divergence: "none",
      ma_bias: "1%", chip_behavior: "flat", operation_observation: "watch",
    },
    candle_patterns: [], chart_patterns: [],
    multi_timeframe: {
      daily: { timeframe: "day", trend_direction: "up", strength: "mid" },
      weekly: { timeframe: "week", trend_direction: "up", strength: "mid" },
      monthly: { timeframe: "month", trend_direction: "up", strength: "mid" },
    },
    quote: {
      symbol, name: "Test", price: 112, change: 4, change_pct: 3.7,
      open: 108, high: 115, low: 105, yesterday_close: 108,
      volume: 20000, timestamp: "2026-05-16T10:00:00+08:00", trade_date: "2026-05-16",
      best_bid: [111], best_ask: [112], best_bid_vol: [100, 50], best_ask_vol: [80, 40],
      is_market_open: false, is_estimated_price: false, price_label: "last", estimated_price: null,
    },
    bid_ask: null, chip: null, chip_recent_df: [], chip_error: null,
    intraday_df: intradayBars, intraday_snapshot: null, intraday_error: null,
    analysis: { industry_overview: [], company_overview: [], volume_price_analysis: "", scenarios: [], conclusion: "" },
  };
}

function defaultUseDashboardImpl(symbol: string | null) {
  return {
    data: symbol ? buildPayload(symbol) : undefined,
    error: undefined,
    isLoading: false,
    mutate: mutateMock,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("13-A: Dashboard 分析入口與日線定位整理", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateGlobalMock.mockResolvedValue(undefined);
    apiGetMock.mockResolvedValue({
      data: { finmind: true, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });
    useDashboardImpl.mockImplementation(defaultUseDashboardImpl);
  });

  // Helper: wait until the dashboard has data (symbol initialised + payload fetched).
  async function waitForDashboard() {
    await screen.findByTestId("candlestick-chart");
  }

  describe("UI changes", () => {
    it("hides the analyze button", async () => {
      render(<DashboardPageClient />);
      await waitForDashboard();
      expect(screen.queryByRole("button", { name: /分析/ })).not.toBeInTheDocument();
    });

    it("hides the realtime-update button", async () => {
      render(<DashboardPageClient />);
      await waitForDashboard();
      expect(screen.queryByRole("button", { name: /即時更新/ })).not.toBeInTheDocument();
    });

    it("shows the Enter hint text", async () => {
      render(<DashboardPageClient />);
      // Hint must be visible from the very first render (before data arrives).
      expect(screen.getByText("輸入代碼後按 Enter 更新資料並分析")).toBeInTheDocument();
    });
  });

  describe("Enter behavior", () => {
    it("entering a different symbol changes the dashboard request", async () => {
      render(<DashboardPageClient />);
      await waitForDashboard();

      const input = screen.getByTestId("stock-selector-input");
      fireEvent.change(input, { target: { value: "3293" } });
      fireEvent.keyDown(input, { key: "Enter" });

      await waitFor(() => {
        expect(useDashboardImpl).toHaveBeenCalledWith("3293", "tw");
      });
    });

    it("entering the same symbol calls mutate() to revalidate", async () => {
      render(<DashboardPageClient />);
      await waitForDashboard();

      // Initial symbol is "2330" (from readLastSymbol default).
      await waitFor(() => {
        expect(useDashboardImpl).toHaveBeenCalledWith("2330", "tw");
      });

      const input = screen.getByTestId("stock-selector-input");
      // Input value is already "2330"; press Enter without changing it.
      fireEvent.keyDown(input, { key: "Enter" });

      await waitFor(() => {
        expect(mutateMock).toHaveBeenCalled();
      });
    });
  });

  describe("分K tab visibility", () => {
    it("hides the 分K tab when intraday_df is empty", async () => {
      // Default buildPayload has intraday_df: [] → no 分K.
      render(<DashboardPageClient />);
      await waitForDashboard();
      expect(screen.queryByRole("button", { name: "分 K" })).not.toBeInTheDocument();
    });

    it("shows the 分K tab when intraday_df has data", async () => {
      useDashboardImpl.mockImplementation((symbol: string | null) => ({
        data: symbol ? buildPayload(symbol, [buildBar(symbol)]) : undefined,
        error: undefined,
        isLoading: false,
        mutate: mutateMock,
      }));

      render(<DashboardPageClient />);
      await waitForDashboard();
      expect(await screen.findByRole("button", { name: "分 K" })).toBeInTheDocument();
    });

    it("auto-switches from minute to day when new payload has no intraday data", async () => {
      // Start: symbol "2330" has intraday data → 分K tab is visible.
      useDashboardImpl.mockImplementation((symbol: string | null) => ({
        data: symbol
          ? buildPayload(symbol, symbol === "2330" ? [buildBar(symbol)] : [])
          : undefined,
        error: undefined,
        isLoading: false,
        mutate: mutateMock,
      }));

      render(<DashboardPageClient />);
      const minuteBtn = await screen.findByRole("button", { name: "分 K" });
      fireEvent.click(minuteBtn);

      // Switch to symbol "3293" which has no intraday → minute fallback should fire.
      const input = screen.getByTestId("stock-selector-input");
      fireEvent.change(input, { target: { value: "3293" } });
      fireEvent.keyDown(input, { key: "Enter" });

      // 分K tab should disappear (no intraday for 3293) and minute state should have reverted.
      await waitFor(() => {
        expect(screen.queryByRole("button", { name: "分 K" })).not.toBeInTheDocument();
      });
    });
  });
});
