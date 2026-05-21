import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";
import { TokenSetupDialog } from "@/components/dashboard/token-setup-dialog";
import { ApiClientError } from "@/lib/api-client";
import type { Market } from "@/types/market";

const apiGetMock = vi.fn();
const apiPostMock = vi.fn();
const mutateGlobalMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock, push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

vi.mock("swr", async (importOriginal) => {
  const actual = await importOriginal<typeof import("swr")>();
  return {
    ...actual,
    mutate: (...args: unknown[]) => mutateGlobalMock(...args),
  };
});

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    apiGet: (...args: unknown[]) => apiGetMock(...args),
    apiPost: (...args: unknown[]) => apiPostMock(...args),
  };
});

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: () => ({
    data: undefined,
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

vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ onChange }: { onChange: (next: Market) => void }) => (
    <button type="button" onClick={() => onChange("tw")}>TW</button>
  ),
}));

vi.mock("@/components/stock-selector", () => ({
  StockSelector: ({
    value,
    onInputChange,
  }: {
    value: string;
    onInputChange: (next: string) => void;
  }) => (
    <input
      aria-label="stock-input"
      value={value}
      onChange={(event) => onInputChange(event.target.value)}
    />
  ),
}));

vi.mock("@/components/dashboard/candlestick-chart", () => ({
  CandlestickChart: () => <div data-testid="candlestick-chart" />,
}));

describe("TokenSetupDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGetMock.mockResolvedValue({
      data: { finmind: true, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });
    mutateGlobalMock.mockResolvedValue(undefined);
  });

  it("renders title and blocks empty save", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存並繼續" })).toBeDisabled();
  });

  it("does not render close button X", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    expect(screen.queryByRole("button", { name: "關閉" })).not.toBeInTheDocument();
  });

  it("renders FinMind links with exact href and external target", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    const website = screen.getByRole("link", { name: "FinMind 官網" });
    const tokenPage = screen.getByRole("link", { name: "取得 API Token" });
    expect(website).toHaveAttribute("href", "https://finmindtrade.com/analysis/#/data/api");
    expect(tokenPage).toHaveAttribute("href", "https://finmindtrade.com/analysis/#/account/user");
    expect(website).toHaveAttribute("target", "_blank");
    expect(website).toHaveAttribute("rel", "noopener noreferrer");
    expect(tokenPage).toHaveAttribute("target", "_blank");
    expect(tokenPage).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not close when pressing Escape", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.keyDown(screen.getByTestId("token-setup-content"), { key: "Escape" });
    expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
  });

  it("does not close when clicking overlay", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.pointerDown(screen.getByTestId("token-setup-overlay"));
    fireEvent.click(screen.getByTestId("token-setup-overlay"));
    expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
  });

  it("toggles FinMind input visibility", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    const input = screen.getByLabelText("FinMind Token");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "顯示 FinMind Token" }));
    expect(input).toHaveAttribute("type", "text");
  });

  it("expands optional AI keys section", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    expect(screen.queryByLabelText("Anthropic API Key")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "AI API Keys（選填）" }));
    expect(screen.getByLabelText("Anthropic API Key")).toBeInTheDocument();
    expect(screen.getByLabelText("OpenAI API Key")).toBeInTheDocument();
    expect(screen.getByLabelText("Gemini API Key")).toBeInTheDocument();
  });

  it("enables save after FinMind token entered", () => {
    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    expect(screen.getByRole("button", { name: "儲存並繼續" })).toBeEnabled();
  });

  it("posts validate request and omits blank AI keys", async () => {
    const onSaved = vi.fn();
    apiPostMock.mockResolvedValue({ data: { updated: true }, meta: {} });

    render(<TokenSetupDialog open onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "AI API Keys（選填）" }));
    fireEvent.change(screen.getByLabelText("OpenAI API Key"), { target: { value: "sk-openai" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith("/api/config/secrets/validate", {
        finmind: "fm-token",
        openai: "sk-openai",
      });
      expect(onSaved).toHaveBeenCalledTimes(1);
    });
  });

  it("shows invalid-token error and keeps dialog open", async () => {
    apiPostMock.mockRejectedValue(
      new ApiClientError(400, "FINMIND_TOKEN_INVALID", "Token 無效"),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "bad-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("Token 無效，請確認從 FinMind 使用者資訊頁複製正確。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
  });

  it("shows unreachable error", async () => {
    apiPostMock.mockRejectedValue(
      new ApiClientError(502, "FINMIND_UNREACHABLE", "連線失敗"),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("無法連線至 FinMind 伺服器，請檢查網路後重試。")).toBeInTheDocument();
  });

  it("shows required-token error for FINMIND_REQUIRED", async () => {
    apiPostMock.mockRejectedValue(
      new ApiClientError(400, "FINMIND_REQUIRED", "FinMind token required"),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("FinMind Token 為必填")).toBeInTheDocument();
  });

  it("shows ApiClientError message for unknown error code", async () => {
    apiPostMock.mockRejectedValue(
      new ApiClientError(500, "UNKNOWN", "後端未知錯誤"),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("後端未知錯誤")).toBeInTheDocument();
  });

  it("shows generic failure message for non-ApiClientError", async () => {
    apiPostMock.mockRejectedValue(new Error("boom"));

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("儲存失敗，請稍後重試。")).toBeInTheDocument();
  });

  it("disables inputs while saving", async () => {
    apiPostMock.mockImplementation(
      () => new Promise(() => undefined),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(screen.getByLabelText("FinMind Token")).toBeDisabled();
    expect(screen.getByRole("button", { name: "儲存中..." })).toBeDisabled();
    expect(screen.getByTestId("token-setup-saving-spinner")).toBeInTheDocument();
  });

  it("sends trimmed values for finmind and optional keys", async () => {
    const onSaved = vi.fn();
    apiPostMock.mockResolvedValue({ data: { updated: true }, meta: {} });

    render(<TokenSetupDialog open onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "  fm-token  " } });
    fireEvent.click(screen.getByRole("button", { name: "AI API Keys（選填）" }));
    fireEvent.change(screen.getByLabelText("Anthropic API Key"), { target: { value: "  ant-token  " } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith("/api/config/secrets/validate", {
        finmind: "fm-token",
        anthropic: "ant-token",
      });
    });
  });
});

describe("Dashboard token onboarding integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateGlobalMock.mockResolvedValue(undefined);
    apiPostMock.mockResolvedValue({ data: { updated: true }, meta: {} });
  });

  it("opens token dialog when finmind token is missing", async () => {
    apiGetMock.mockResolvedValue({
      data: { finmind: false, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });

    render(<DashboardPageClient />);

    expect(await screen.findByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    expect(apiGetMock).toHaveBeenCalledWith("/api/config/secrets/status");
  });

  it("does not show modal on first failure while retries are pending", async () => {
    apiGetMock.mockRejectedValue(new Error("network"));

    render(<DashboardPageClient />);

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith("/api/config/secrets/status");
    });
    // Retries still in progress; modal must not flash before all 5 attempts finish
    expect(screen.queryByRole("heading", { name: "設定 API Token" })).not.toBeInTheDocument();
  });

  describe("retry exhaustion (fake timers)", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.clearAllTimers();
      vi.useRealTimers();
    });

    it("forces token modal after all 5 retries fail", async () => {
      apiGetMock.mockRejectedValue(new Error("network"));
      render(<DashboardPageClient />);
      // 4 delays × 1 s between 5 attempts = 4 000 ms total; advance 5 s to be safe
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    });

    it("shows modal when a retry succeeds with finmind: false", async () => {
      apiGetMock
        .mockRejectedValueOnce(new Error("network"))
        .mockResolvedValue({
          data: { finmind: false, openai: false, anthropic: false, gemini: false, google: false },
          meta: {},
        });
      render(<DashboardPageClient />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });
      expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    });
  });

  it("closes dialog and triggers global mutate + refresh on save success", async () => {
    apiGetMock.mockResolvedValue({
      data: { finmind: false, openai: false, anthropic: false, gemini: false, google: false },
      meta: {},
    });

    render(<DashboardPageClient />);
    fireEvent.change(await screen.findByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => {
      expect(mutateGlobalMock).toHaveBeenCalled();
      expect(refreshMock).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByRole("heading", { name: "設定 API Token" })).not.toBeInTheDocument();
  });
});
