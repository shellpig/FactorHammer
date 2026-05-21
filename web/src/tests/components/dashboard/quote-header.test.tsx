import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getPrevCloseColor } from "@/components/dashboard/candlestick-chart";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";
import type { DashboardPayloadResponse, OhlcvBar } from "@/types/analysis";
import type { Market } from "@/types/market";

// ── Mocks ──────────────────────────────────────────────────────────────────
const apiGetMock = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    apiGet: (...args: unknown[]) => apiGetMock(...args),
  };
});

vi.mock("@/components/dashboard/candlestick-chart", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/dashboard/candlestick-chart")>();
  return {
    ...actual,
    CandlestickChart: () => <div data-testid="candlestick-chart" />,
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

vi.mock("@/hooks/use-command-palette", () => ({
  useCommandPaletteEntry: () => undefined,
  useCommandPaletteStore: () => ({ open: false, setOpen: vi.fn(), entries: [] }),
}));

vi.mock("@/components/providers", () => ({
  Providers: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ onChange }: { onChange: (m: Market) => void }) => (
    <button type="button" onClick={() => onChange("tw")}>TW</button>
  ),
}));

vi.mock("@/components/stock-selector", () => ({
  StockSelector: ({ value, onInputChange }: { value: string; onInputChange: (v: string) => void }) => (
    <input aria-label="stock-input" value={value} onChange={(e) => onInputChange(e.target.value)} />
  ),
}));

function buildBars(symbol: string): OhlcvBar[] {
  return [
    { date: "2026-05-15T00:00:00+08:00", open: 100, high: 110, low: 95, close: 108, volume: 1000000, symbol },
    { date: "2026-05-16T00:00:00+08:00", open: 108, high: 115, low: 105, close: 112, volume: 1500000, symbol },
  ];
}

function buildPayload(symbol: string, yesterdayClose: number): DashboardPayloadResponse {
  return {
    symbol,
    market: "tw",
    subject_name: "Test",
    analysis_time: "2026-05-16 10:00:00",
    ai_enabled: false,
    daily_df: buildBars(symbol),
    technical: {
      trend_direction: "up", ma_status: "up", kd_status: "bull", macd_status: "bull",
      volume_status: "normal", volume_price_relation: "up", short_term_score: 0.7,
      short_term_label: "bull", short_term_components: { ma: 0.7, kd: 0.7, volume_price: 0.7, breakout: 0.7 },
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
      open: 108, high: 115, low: 105, yesterday_close: yesterdayClose,
      volume: 20000, timestamp: "2026-05-16T10:00:00+08:00", trade_date: "2026-05-16",
      best_bid: [111], best_ask: [112], best_bid_vol: [100, 50], best_ask_vol: [80, 40],
      is_market_open: true, is_estimated_price: false, price_label: "last", estimated_price: null,
    },
    bid_ask: null, chip: null, chip_recent_df: [], chip_error: null,
    intraday_df: [], intraday_snapshot: null, intraday_error: null,
    analysis: { industry_overview: [], company_overview: [], volume_price_analysis: "", scenarios: [], conclusion: "" },
  };
}

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: (symbol: string | null) => ({
    data: symbol ? buildPayload("2330", 108) : undefined,
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
  }),
}));

vi.mock("@/lib/hooks/useP11Valuation", () => ({ useP11Valuation: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11MonthlyRevenue", () => ({ useP11MonthlyRevenue: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11DividendHistory", () => ({ useP11DividendHistory: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11IndustryPer", () => ({ useP11IndustryPer: () => ({ data: undefined, isLoading: false }) }));
vi.mock("@/lib/hooks/useP11InstitutionalCost", () => ({ useP11InstitutionalCost: () => ({ data: undefined }) }));
vi.mock("@/lib/hooks/useP11EventCalendar", () => ({ useP11EventCalendar: () => ({ data: undefined, mutate: vi.fn() }) }));

// ── Tests ──────────────────────────────────────────────────────────────────
describe("Quote header — Phase 11-E", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGetMock.mockResolvedValue({
      data: { finmind: true, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });
  });

  describe("11-E-F5: single-row quote layout", () => {
    it("renders quote-header-row as a single section", async () => {
      render(<DashboardPageClient />);
      // Dashboard fetch is gated on secrets/status (P12-C-onboarding-race); await render.
      expect(await screen.findByTestId("quote-header-row")).toBeInTheDocument();
    });

    it("shows all 7 quote fields with muted labels", async () => {
      render(<DashboardPageClient />);
      const row = await screen.findByTestId("quote-header-row");
      // All 7 labels should be present
      const labels = ["開盤", "最高", "最低", "前收", "日K成交量", "買量", "賣量"];
      for (const label of labels) {
        expect(row).toHaveTextContent(label);
      }
    });

    it("label elements have muted class", async () => {
      render(<DashboardPageClient />);
      const row = await screen.findByTestId("quote-header-row");
      const muteSpans = row.querySelectorAll(".text-slate-500");
      // At least 5 muted labels (開盤/最高/最低/前收/日K成交量; 買量/賣量 may vary)
      expect(muteSpans.length).toBeGreaterThanOrEqual(5);
    });
  });

  describe("11-E-F6: getPrevCloseColor helper", () => {
    it("returns up color (red for TW) when price > prevClose", () => {
      const color = getPrevCloseColor(112, 108, "tw");
      // TW up color is red
      expect(color).toBe("#ef4444");
    });

    it("returns down color (green for TW) when price < prevClose", () => {
      const color = getPrevCloseColor(105, 108, "tw");
      // TW down color is green
      expect(color).toBe("#22c55e");
    });

    it("returns gray when price === prevClose", () => {
      const color = getPrevCloseColor(108, 108, "tw");
      expect(color).toBe("#64748b");
    });

    it("returns gray when currentPrice is undefined", () => {
      const color = getPrevCloseColor(undefined, 108, "tw");
      expect(color).toBe("#64748b");
    });

    it("returns gray when previousClose is undefined (no prior bar)", () => {
      const color = getPrevCloseColor(108, undefined, "tw");
      expect(color).toBe("#64748b");
    });

    it("returns up color (green for US) when price > prevClose", () => {
      const color = getPrevCloseColor(210, 208, "us");
      // US up color is green
      expect(color).toBe("#22c55e");
    });
  });
});
