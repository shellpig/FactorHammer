import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";
import { ValuationPanel } from "@/components/dashboard/p11/valuation-panel";
import { MonthlyRevenuePanel } from "@/components/dashboard/p11/monthly-revenue-panel";
import { P11_TOOLTIP_TEXT } from "@/components/dashboard/tooltip-text";
import type { DashboardPayloadResponse, OhlcvBar } from "@/types/analysis";
import type { Market } from "@/types/market";

const apiGetMock = vi.fn();
const mockMutate = vi.fn();
let mockLoading = false;

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    apiGet: (...args: unknown[]) => apiGetMock(...args),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

function buildBars(symbol: string): OhlcvBar[] {
  return [
    {
      date: "2026-05-15T00:00:00+08:00",
      open: 100,
      high: 110,
      low: 95,
      close: 108,
      volume: 1200000,
      symbol,
    },
    {
      date: "2026-05-16T00:00:00+08:00",
      open: 108,
      high: 112,
      low: 104,
      close: 111,
      volume: 1500000,
      symbol,
    },
  ];
}

function buildPayload(market: Market, symbol: string): DashboardPayloadResponse {
  return {
    symbol,
    market,
    subject_name: market === "tw" ? "TSMC" : "Apple Inc",
    analysis_time: "2026-05-17 10:00:00",
    ai_enabled: true,
    daily_df: buildBars(symbol),
    technical: {
      trend_direction: "up",
      ma_status: "up",
      kd_status: "bull",
      macd_status: "bull",
      volume_status: "normal",
      volume_price_relation: "up",
      short_term_score: 0.76,
      short_term_label: "bull",
      short_term_components: { ma: 0.8, kd: 0.7, volume_price: 0.8, breakout: 0.7 },
      resistance_levels: [
        { value: 533, label: "R1", kind: "swing_high" },
        { value: 30.43, label: "R2", kind: "swing_high" },
      ],
      support_levels: [
        { value: 28.42, label: "S1", kind: "ma20" },
        { value: 23.07, label: "S2", kind: "swing_low" },
      ],
      volume_price_divergence: "none",
      ma_bias: "2.1%",
      chip_behavior: "flat",
      operation_observation: "watch 20MA",
    },
    candle_patterns: [{ name: "hammer", detected: true, description: "desc" }],
    chart_patterns: [{ pattern_type: "W", formed: false, description: "desc", key_points: [] }],
    multi_timeframe: {
      daily: { timeframe: "day", trend_direction: "up", strength: "strong" },
      weekly: { timeframe: "week", trend_direction: "up", strength: "mid" },
      monthly: { timeframe: "month", trend_direction: "up", strength: "mid" },
    },
    quote:
      market === "tw"
        ? {
            symbol,
            name: "TSMC",
            price: 111,
            change: 3,
            change_pct: 2.78,
            open: 108,
            high: 112,
            low: 104,
            yesterday_close: 108,
            volume: 30000,
            timestamp: "2026-05-17T10:00:00+08:00",
            trade_date: "2026-05-17",
            best_bid: [110],
            best_ask: [111],
            best_bid_vol: [100, 50],
            best_ask_vol: [90, 45],
            is_market_open: true,
            is_estimated_price: false,
            price_label: "last",
            estimated_price: null,
          }
        : null,
    bid_ask: market === "tw" ? { total_bid_vol: 150, total_ask_vol: 135, bid_ratio: 0.53, ask_ratio: 0.47, label: "balanced" } : null,
    chip:
      market === "tw"
        ? {
            foreign_net_n_days: 1000,
            trust_net_n_days: 200,
            dealer_net_n_days: -100,
            foreign_label: "+1,000",
            trust_label: "+200",
            dealer_label: "-100",
            chip_concentration: "up",
            chip_trend: "up",
            chip_description: "desc",
            margin_balance_change: 300,
            short_balance_change: -120,
          }
        : null,
    chip_recent_df:
      market === "tw"
        ? [{ "日期": "2026-05-16", "外資": 1200, "投信": 200, "自營商": -100 }]
        : [],
    chip_error: null,
    intraday_df: market === "us" ? buildBars(symbol) : [],
    intraday_snapshot:
      market === "us"
        ? {
            symbol,
            price: 210.5,
            previous_raw_close: 208.2,
            change: 2.3,
            change_pct: 1.1,
            volume: 5200000,
            timestamp: "2026-05-17T10:00:00-04:00",
            source: "yfinance",
            interval: "1m",
          }
        : null,
    intraday_error: null,
    analysis: {
      industry_overview: ["x"],
      company_overview: ["x"],
      volume_price_analysis: "x",
      scenarios: [{ name: "long", entry_range: "108-110", stop_loss: 104, target: "115" }],
      conclusion: "x",
    },
  };
}

const twPayload = buildPayload("tw", "2330");
const usPayload = buildPayload("us", "AAPL");

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: (symbol: string | null, market: Market) => {
    if (mockLoading) {
      return { data: undefined, error: undefined, isLoading: true, mutate: mockMutate };
    }
    if (!symbol) {
      return { data: undefined, error: undefined, isLoading: false, mutate: mockMutate };
    }
    return { data: market === "tw" ? twPayload : usPayload, error: undefined, isLoading: false, mutate: mockMutate };
  },
}));

vi.mock("@/components/dashboard/candlestick-chart", () => ({
  CandlestickChart: () => <div data-testid="candlestick-chart" />,
}));

vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ onChange }: { onChange: (next: Market) => void }) => (
    <div>
      <button type="button" onClick={() => onChange("tw")}>TW</button>
      <button type="button" onClick={() => onChange("us")}>US</button>
    </div>
  ),
}));

vi.mock("@/components/stock-selector", () => ({
  StockSelector: ({ value, onInputChange }: { value: string; onInputChange: (next: string) => void }) => (
    <input aria-label="stock-input" value={value} onChange={(event) => onInputChange(event.target.value)} />
  ),
}));

vi.mock("@/lib/hooks/useP11Valuation", () => ({
  useP11Valuation: () => ({
    data: { symbol: "2330", market: "tw", date: "2026-05-17", per: 20.5, pbr: 4.1, dividend_yield: 2.3, industry: "Semi" },
  }),
}));

vi.mock("@/lib/hooks/useP11MonthlyRevenue", () => ({
  useP11MonthlyRevenue: () => ({
    data: {
      symbol: "2330",
      market: "tw",
      latest_month: "2026-04",
      latest_revenue: 300000000000,
      items: Array.from({ length: 12 }, (_, i) => ({
        date: `2026-${String(i + 1).padStart(2, "0")}-10`,
        revenue: 200000000000 + i * 1000000000,
        revenue_year: 2026,
        revenue_month: i + 1,
        yoy: 5 + i,
        mom: i - 2,
      })),
    },
  }),
}));

vi.mock("@/lib/hooks/useP11DividendHistory", () => ({
  useP11DividendHistory: () => ({
    data: { symbol: "2330", market: "tw", items: [{ date: "2026-06-15", cash_dividend: 3.5, ttm_pe: 12.5 }] },
  }),
}));

vi.mock("@/lib/hooks/useP11IndustryPer", () => ({
  useP11IndustryPer: () => ({
    data: {
      symbol: "2330",
      market: "tw",
      industry: "Semi",
      median: 18,
      mean: 19,
      count: 1,
      items: [{ symbol: "2330", name: "TSMC", date: "2026-05-17", per: 20, pbr: 4, dividend_yield: 2, is_current: true }],
      cached_at: "2026-05-17T10:00:00+08:00",
    },
    isLoading: false,
  }),
}));

vi.mock("@/lib/hooks/useP11InstitutionalCost", () => ({
  useP11InstitutionalCost: () => ({
    data: {
      symbol: "2330",
      market: "tw",
      days: 30,
      current_price: 110,
      foreign: { cost: 100, pnl: 10 },
      trust: { cost: 95, pnl: 15 },
      dealer: { cost: null, pnl: null },
    },
  }),
}));

vi.mock("@/lib/hooks/useP11EventCalendar", () => ({
  useP11EventCalendar: () => ({
    data: {
      symbol: "2330",
      market: "tw",
      next_ex_dividend: { date: "2026-06-20", cash_dividend: 3.5, days_until: 10, is_estimated: false },
      last_ex_dividend: { date: "2025-06-15", cash_dividend: 3.2 },
      next_shareholder_meeting: { date: "2026-06-30", meeting_type: "常會", source: "manual", is_manual: true, days_until: 20 },
      last_shareholder_meeting: null,
      missing_shareholder_meeting: false,
    },
    mutate: vi.fn(),
  }),
}));

describe("P11 panels", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoading = false;
    apiGetMock.mockResolvedValue({
      data: { finmind: true, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });
  });

  it("renders 11-B + 11-C panels for TW market", () => {
    render(<DashboardPageClient />);
    expect(screen.getByTestId("p11-panel-pe-ratio")).toBeInTheDocument();
    expect(screen.getByTestId("p11-panel-monthly-revenue")).toBeInTheDocument();
    expect(screen.getByTestId("p11-panel-historical-dividend-pe")).toBeInTheDocument();
    expect(screen.getByTestId("p11-panel-institutional-cost")).toBeInTheDocument();
    expect(screen.getByTestId("p11-panel-event-calendar")).toBeInTheDocument();
  });

  it("11-E-F8: retail-sentiment placeholder is removed", () => {
    render(<DashboardPageClient />);
    expect(screen.queryByTestId("p11-panel-retail-sentiment")).not.toBeInTheDocument();
    expect(screen.queryByText("散戶多空比")).not.toBeInTheDocument();
  });

  it("11-E-F3: valuation unsupported text uses same amber color as event-calendar warning", () => {
    render(
      <ValuationPanel
        data={{ symbol: "0056", market: "tw", date: "2026-05-18", per: null, pbr: null, dividend_yield: null, industry: "ETF" }}
        onOpenIndustry={() => undefined}
      />
    );
    const el = screen.getByTestId("p11-valuation-unsupported");
    expect(el).toHaveClass("text-amber-300");
    expect(el).not.toHaveClass("text-slate-500");
  });

  it("11-E-F3: monthly-revenue unsupported text uses same amber color as event-calendar warning", () => {
    render(
      <MonthlyRevenuePanel
        data={{ symbol: "0056", market: "tw", latest_month: null, latest_revenue: null, items: [] }}
      />
    );
    const el = screen.getByTestId("p11-monthly-revenue-unsupported");
    expect(el).toHaveClass("text-amber-300");
    expect(el).not.toHaveClass("text-slate-500");
  });

  it("renders tooltip trigger for each 11-B panel title", () => {
    render(<DashboardPageClient />);
    expect(screen.getByLabelText(P11_TOOLTIP_TEXT.pe_ratio)).toBeInTheDocument();
    expect(screen.getByLabelText(P11_TOOLTIP_TEXT.monthly_revenue)).toBeInTheDocument();
    expect(screen.getByLabelText(P11_TOOLTIP_TEXT.historical_dividend_pe)).toBeInTheDocument();
  });

  it("opens same-industry modal without triggering dashboard mutate", () => {
    render(<DashboardPageClient />);
    fireEvent.click(screen.getByRole("button", { name: "同產業 ->" }));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not render P11 block in US market", () => {
    render(<DashboardPageClient />);
    fireEvent.click(screen.getByRole("button", { name: "US" }));
    fireEvent.change(screen.getByLabelText("stock-input"), { target: { value: "AAPL" } });
    fireEvent.click(screen.getByRole("button", { name: "分析" }));
    expect(screen.queryByTestId("p11-panel-pe-ratio")).not.toBeInTheDocument();
    expect(screen.queryByTestId("p11-panel-monthly-revenue")).not.toBeInTheDocument();
  });

  it("uses 300px chart loading skeleton height", () => {
    mockLoading = true;
    render(<DashboardPageClient />);
    expect(screen.getByTestId("dashboard-chart-skeleton")).toHaveClass("h-[300px]");
  });

  it("renders compact inline rows in chip panel", () => {
    render(<DashboardPageClient />);
    expect(screen.getByTestId("chip-bid-ask-inline")).toHaveTextContent("53.00% /");
    expect(screen.getByTestId("chip-margin-inline")).toHaveTextContent("+300");
    expect(screen.getByTestId("chip-short-inline")).toHaveTextContent("-120");
  });

  it("formats TW levels by tick size (high price no decimals)", () => {
    render(<DashboardPageClient />);
    expect(screen.getByText("533 / 30.43")).toBeInTheDocument();
    expect(screen.getByText("28.42 / 23.07")).toBeInTheDocument();
  });
});
