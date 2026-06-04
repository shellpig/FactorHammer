import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ActiveEtfPageClient } from "@/app/active-etf/active-etf-page-client";
import * as hooks from "@/hooks/use-active-etf";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/active-etf",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/use-active-etf", () => ({
  useActiveEtfList: vi.fn(),
  useActiveEtfHoldings: vi.fn(),
}));

describe("ActiveEtfPageClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders unselected state when no ETF is selected", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });
    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: null,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);
    expect(screen.getByText("未選擇 ETF")).toBeInTheDocument();
  });

  it("renders list and loads holdings for selected ETF", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [
        { code: "00981A", name: "主動統一台股增長" },
        { code: "00982A", name: "另一檔主動ETF" },
      ],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const mockHoldings = {
      etf_code: "00981A",
      etf_name: "主動統一台股增長",
      premium: {
        etf_code: "00981A",
        etf_name: "主動統一台股增長",
        market_price: 31.36,
        estimated_nav: 31.25,
        premium_discount_pct: 0.35,
        previous_nav: 31.97,
        data_date: "2026-06-04",
        data_time: "16:59:55",
        source: "twse_mis",
      },
      latest_date: "2026-06-04",
      previous_date: "2026-06-03",
      has_previous: true,
      holdings: [
        {
          rank: 1,
          holding_code: "2330.TW",
          holding_name: "台積電",
          shares: 1000,
          weight_pct: 15.5,
          delta_shares: 100,
        },
      ],
      changes: {
        buys: [
          {
            holding_code: "2330.TW",
            holding_name: "台積電",
            delta_shares: 100,
          },
        ],
        sells: [],
        entries: [],
        exits: [],
      },
    };

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: mockHoldings,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);

    // Content should show up
    expect(screen.getByTestId("active-etf-content")).toBeInTheDocument();
    expect(screen.getByTestId("active-etf-title")).toHaveClass("text-lg");
    expect(screen.getByTestId("active-etf-title")).toHaveTextContent("00981A 主動統一台股增長");
    expect(screen.getByTestId("active-etf-premium-metrics")).toHaveTextContent("成交價 31.36");
    expect(screen.getByTestId("active-etf-premium-metrics")).toHaveTextContent("預估淨值 31.25");
    expect(screen.getByTestId("active-etf-premium-metrics")).toHaveTextContent("預估折溢價 0.35%");
    expect(screen.getByTestId("active-etf-data-date")).toHaveTextContent("資料日期：2026-06-04");
    expect(screen.getByTestId("active-etf-panel-grid")).toHaveClass("xl:grid-cols-[minmax(320px,0.88fr)_minmax(560px,1.12fr)]");
    expect(screen.getByTestId("changes-panel-title")).toHaveTextContent("持股變動");
    expect(screen.getByTestId("changes-panel-subtitle")).toHaveTextContent("比較區間：2026-06-03 → 2026-06-04");

    // Table elements
    expect(screen.getAllByText("台積電").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2330.TW").length).toBeGreaterThan(0);
    expect(screen.getByText("15.50%")).toBeInTheDocument();
  });

  it("shows -- for all premium metrics when premium is null", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const mockHoldings = {
      etf_code: "00981A",
      etf_name: "主動統一台股增長",
      premium: null,
      latest_date: "2026-06-04",
      previous_date: null,
      has_previous: false,
      holdings: [],
      changes: {
        buys: [],
        sells: [],
        entries: [],
        exits: [],
      },
    };

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: mockHoldings,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);

    const premiumMetrics = screen.getByTestId("active-etf-premium-metrics");
    expect(premiumMetrics).toHaveTextContent("成交價 --");
    expect(premiumMetrics).toHaveTextContent("預估淨值 --");
    expect(premiumMetrics).toHaveTextContent("預估折溢價 --");
  });

  it("shows -- for individual null premium fields while rendering valid ones", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const mockHoldings = {
      etf_code: "00981A",
      etf_name: "主動統一台股增長",
      premium: {
        etf_code: "00981A",
        etf_name: "主動統一台股增長",
        market_price: null,
        estimated_nav: 31.25,
        premium_discount_pct: null,
        previous_nav: null,
        data_date: "2026-06-04",
        data_time: "16:59:55",
        source: "twse_mis",
      },
      latest_date: "2026-06-04",
      previous_date: null,
      has_previous: false,
      holdings: [],
      changes: {
        buys: [],
        sells: [],
        entries: [],
        exits: [],
      },
    };

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: mockHoldings,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);

    const premiumMetrics = screen.getByTestId("active-etf-premium-metrics");
    expect(premiumMetrics).toHaveTextContent("成交價 --");
    expect(premiumMetrics).toHaveTextContent("預估淨值 31.25");
    expect(premiumMetrics).toHaveTextContent("預估折溢價 --");
  });

  it("handles loading and error states for holdings", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: null,
      isLoading: true,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const { rerender } = render(<ActiveEtfPageClient />);
    expect(screen.getAllByTestId("table-skeleton").length).toBeGreaterThan(0);

    // Error state
    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: null,
      isLoading: false,
      isError: true,
      error: new Error("Fetcher failure"),
      mutate: vi.fn(),
    });

    rerender(<ActiveEtfPageClient />);
    expect(screen.getByText("載入資料失敗")).toBeInTheDocument();
  });

  it("handles selector switching and persists in localStorage", async () => {
    const mockMutate = vi.fn();
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [
        { code: "00981A", name: "主動統一台股增長" },
        { code: "00982A", name: "另一檔主動ETF" },
      ],
      isLoading: false,
      isError: false,
      error: null,
      mutate: mockMutate,
    });

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: null,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(<ActiveEtfPageClient />);

    const selector = screen.getByTestId("active-etf-selector") as HTMLSelectElement;
    expect(selector.value).toBe("00981A");

    const { fireEvent } = await import("@testing-library/react");
    fireEvent.change(selector, { target: { value: "00982A" } });

    expect(setItemSpy).toHaveBeenCalledWith("qt-last-active-etf", "00982A");
  });

  it("renders new entry and exit badges in the changes panel", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const mockHoldings = {
      etf_code: "00981A",
      etf_name: "主動統一台股增長",
      latest_date: "2026-06-04",
      previous_date: "2026-06-03",
      has_previous: true,
      holdings: [],
      changes: {
        buys: [],
        sells: [],
        entries: [
          {
            holding_code: "2330.TW",
            holding_name: "台積電",
            delta_shares: 500,
          },
        ],
        exits: [
          {
            holding_code: "2308.TW",
            holding_name: "台達電",
            delta_shares: -200,
          },
        ],
      },
    };

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: mockHoldings,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);

    expect(screen.getByText("新進")).toBeInTheDocument();
    expect(screen.getByText("剔除")).toBeInTheDocument();
    expect(screen.getByText("+500 股")).toBeInTheDocument();
    expect(screen.getByText("-200 股")).toBeInTheDocument();
    expect(screen.getByTestId("buy-section-title")).toHaveClass("text-red-500");
    expect(screen.getByTestId("sell-section-title")).toHaveClass("text-emerald-500");
    expect(screen.getByTestId("buy-delta")).toHaveClass("text-red-500");
    expect(screen.getByTestId("sell-delta")).toHaveClass("text-emerald-500");
  });

  it("renders has_previous=false fallback text on first capture", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const mockHoldings = {
      etf_code: "00981A",
      etf_name: "主動統一台股增長",
      latest_date: "2026-06-04",
      previous_date: null,
      has_previous: false,
      holdings: [],
      changes: {
        buys: [],
        sells: [],
        entries: [],
        exits: [],
      },
    };

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: mockHoldings,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    render(<ActiveEtfPageClient />);

    expect(screen.getByTestId("no-prev-data-msg")).toHaveTextContent(
      "首次擷取，尚無前次資料可比較。"
    );
    expect(screen.getByText("比較區間：首次擷取快照")).toBeInTheDocument();
  });

  it("triggers background sweep on mount when selected code is resolved", () => {
    vi.mocked(hooks.useActiveEtfList).mockReturnValue({
      etfs: [{ code: "00981A", name: "主動統一台股增長" }],
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    vi.mocked(hooks.useActiveEtfHoldings).mockReturnValue({
      holdings: null,
      isLoading: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
    });

    const fetchSpy = vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ status: "started" }), { status: 202 }))
    );

    render(<ActiveEtfPageClient />);

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/active-etf/sweep?skip_code=00981A"),
      expect.objectContaining({ method: "POST" })
    );
  });
});
