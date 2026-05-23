import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPageClient from "@/components/dashboard/dashboard-page-client";
import { TokenSetupDialog } from "@/components/dashboard/token-setup-dialog";
import type { Market } from "@/types/market";

// ── 全域 mock ──────────────────────────────────────────────────────────────
const apiGetMock = vi.fn();
const mutateGlobalMock = vi.fn();
const refreshMock = vi.fn();
const useDashboardMock = vi.fn();

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
  };
});

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: (...args: unknown[]) => {
    useDashboardMock(...args);
    return {
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    };
  },
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

// ── Helper: build a fetch Response ────────────────────────────────────────

function makeValidateOkResponse(extra: Record<string, unknown> = {}) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        data: {
          results: {
            finmind: { status: "ok", message: "FinMind token 驗證成功" },
            ...extra,
          },
          saved: ["finmind", ...Object.keys(extra)],
        },
        meta: {},
      }),
  } as Response);
}

function makeValidateFailResponse(status: ValidationStatus, message: string) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        data: {
          results: { finmind: { status, message } },
          saved: [],
        },
        meta: {},
      }),
  } as Response);
}

function makeHttpErrorResponse(httpStatus: number, message: string) {
  return Promise.resolve({
    ok: false,
    status: httpStatus,
    json: () =>
      Promise.resolve({
        detail: { error: { code: "ENV_WRITE_FAILED", message } },
      }),
  } as Response);
}

type ValidationStatus = "ok" | "invalid_key" | "no_quota" | "unreachable" | "skipped";

// ── TokenSetupDialog ──────────────────────────────────────────────────────

describe("TokenSetupDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", vi.fn());
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/health") {
        return Promise.resolve({ data: { status: "ok" }, meta: {} });
      }
      if (path === "/api/config/secrets/status") {
        return Promise.resolve({
          data: { finmind: true, openai: false, anthropic: false, gemini: false },
          meta: {},
        });
      }
      return Promise.reject(new Error(`unexpected path: ${path}`));
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

  // 15-A-2：新 response shape — HTTP 200 + data.results.finmind.status
  it("posts validate request and calls onSaved on finmind ok", async () => {
    const onSaved = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(makeValidateOkResponse()));

    render(<TokenSetupDialog open onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "AI API Keys（選填）" }));
    fireEvent.change(screen.getByLabelText("OpenAI API Key"), { target: { value: "sk-openai" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        "/api/config/secrets/validate",
        expect.objectContaining({ method: "POST" }),
      );
      expect(onSaved).toHaveBeenCalledTimes(1);
    });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string);
    expect(body.finmind).toBe("fm-token");
    expect(body.openai).toBe("sk-openai");
  });

  it("shows error message when finmind status is invalid_key", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(
        makeValidateFailResponse("invalid_key", "FinMind token 無效"),
      ),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "bad-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("FinMind token 無效")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
  });

  it("shows error message when finmind status is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(
        makeValidateFailResponse("unreachable", "無法連線至 FinMind 伺服器"),
      ),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("無法連線至 FinMind 伺服器")).toBeInTheDocument();
  });

  it("shows error when finmind result is missing from response (malformed)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(
        Promise.resolve({
          ok: true,
          status: 200,
          // missing data.results.finmind
          json: () => Promise.resolve({ data: { results: {}, saved: [] }, meta: {} }),
        } as Response),
      ),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(
      await screen.findByText("驗證服務回應缺少 FinMind 結果，請稍後再試"),
    ).toBeInTheDocument();
  });

  it("shows generic failure on HTTP 5xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(
        makeHttpErrorResponse(500, "寫入設定檔失敗：disk full"),
      ),
    );

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("寫入設定檔失敗：disk full")).toBeInTheDocument();
  });

  it("shows generic failure message for network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("network down")));

    render(<TokenSetupDialog open onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    expect(await screen.findByText("儲存失敗，請稍後重試。")).toBeInTheDocument();
  });

  it("disables inputs while saving", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(new Promise(() => undefined)),
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
    vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(makeValidateOkResponse()));

    render(<TokenSetupDialog open onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "  fm-token  " } });
    fireEvent.click(screen.getByRole("button", { name: "AI API Keys（選填）" }));
    fireEvent.change(screen.getByLabelText("Anthropic API Key"), { target: { value: "  ant-token  " } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => {
      const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string);
      expect(body.finmind).toBe("fm-token");
      expect(body.anthropic).toBe("ant-token");
    });
  });

  it("calls onSaved when finmind status is no_quota (key written)", async () => {
    const onSaved = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValueOnce(
        Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              data: {
                results: { finmind: { status: "no_quota", message: "no quota" } },
                saved: ["finmind"],
              },
              meta: {},
            }),
        } as Response),
      ),
    );

    render(<TokenSetupDialog open onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("FinMind Token"), { target: { value: "fm-token" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存並繼續" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  });
});

// ── Dashboard token onboarding integration ────────────────────────────────

describe("Dashboard token onboarding integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", vi.fn());
    useDashboardMock.mockClear();
    mutateGlobalMock.mockResolvedValue(undefined);
  });

  it("opens token dialog when finmind token is missing", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/health") {
        return Promise.resolve({ data: { status: "ok" }, meta: {} });
      }
      if (path === "/api/config/secrets/status") {
        return Promise.resolve({
          data: { finmind: false, openai: false, anthropic: false, gemini: false },
          meta: {},
        });
      }
      return Promise.reject(new Error(`unexpected path: ${path}`));
    });

    render(<DashboardPageClient />);

    expect(await screen.findByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    expect(apiGetMock).toHaveBeenCalledWith("/api/health");
    expect(apiGetMock).toHaveBeenCalledWith("/api/config/secrets/status");
  });

  it("shows startup overlay while backend health check is pending", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/health") {
        return new Promise(() => undefined);
      }
      return Promise.reject(new Error(`unexpected path: ${path}`));
    });

    render(<DashboardPageClient />);

    expect(await screen.findByTestId("startup-overlay")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "設定 API Token" })).not.toBeInTheDocument();
    expect(apiGetMock).toHaveBeenCalledWith("/api/health");
    expect(apiGetMock).not.toHaveBeenCalledWith("/api/config/secrets/status");
    expect(useDashboardMock.mock.calls.every(([symbol]) => symbol === null)).toBe(true);
  });

  it("does not show modal on first health-check failure while retries are pending", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/health") {
        return Promise.reject(new Error("network"));
      }
      return Promise.reject(new Error(`unexpected path: ${path}`));
    });

    render(<DashboardPageClient />);

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith("/api/health");
    });
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

    it("shows timeout message after backend health retries are exhausted", async () => {
      apiGetMock.mockImplementation((path: string) => {
        if (path === "/api/health") {
          return Promise.reject(new Error("network"));
        }
        return Promise.reject(new Error(`unexpected path: ${path}`));
      });
      render(<DashboardPageClient />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(screen.getByText("後端啟動逾時，請確認 FactorHammer-Backend-8000 視窗是否有錯誤。")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "重新檢查" })).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: "設定 API Token" })).not.toBeInTheDocument();
    });

    it("shows modal when backend retry succeeds and finmind is missing", async () => {
      apiGetMock
        .mockImplementationOnce((path: string) => {
          if (path === "/api/health") return Promise.reject(new Error("network"));
          return Promise.reject(new Error(`unexpected path: ${path}`));
        })
        .mockImplementationOnce((path: string) => {
          if (path === "/api/health") return Promise.resolve({ data: { status: "ok" }, meta: {} });
          return Promise.reject(new Error(`unexpected path: ${path}`));
        })
        .mockImplementationOnce((path: string) => {
          if (path === "/api/config/secrets/status") {
            return Promise.resolve({
              data: { finmind: false, openai: false, anthropic: false, gemini: false },
              meta: {},
            });
          }
          return Promise.reject(new Error(`unexpected path: ${path}`));
        });
      render(<DashboardPageClient />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });
      expect(screen.getByRole("heading", { name: "設定 API Token" })).toBeInTheDocument();
    });
  });

  it("closes dialog and triggers global mutate + refresh on save success", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/health") {
        return Promise.resolve({ data: { status: "ok" }, meta: {} });
      }
      if (path === "/api/config/secrets/status") {
        return Promise.resolve({
          data: { finmind: false, openai: false, anthropic: false, gemini: false },
          meta: {},
        });
      }
      return Promise.reject(new Error(`unexpected path: ${path}`));
    });

    // 15-A-2：stub fetch for the POST /api/config/secrets/validate call
    vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(makeValidateOkResponse()));

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
