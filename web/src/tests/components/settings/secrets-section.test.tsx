// Tests for SecretsSection component (Phase 10-G-2 / 15-A-2)

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ success: mockToastSuccess, error: mockToastError, info: vi.fn(), dismiss: vi.fn() }),
}));

const mockMutate = vi.fn();
const mockUseSecretsStatus = vi.fn();

vi.mock("@/hooks/use-config", () => ({
  useSecretsStatus: (...args: unknown[]) => mockUseSecretsStatus(...args),
  updateSecrets: vi.fn(),
}));

import { SecretsSection } from "@/components/settings/secrets-section";

// 15-A-2：google 欄位已移除
const DEFAULT_STATUS_RETURN = {
  status: { openai: true, anthropic: false, gemini: false, deepseek: false, finmind: false },
  isLoading: false,
  mutate: mockMutate,
};

// Helper to build a fetch mock response
function mockFetchResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

describe("SecretsSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSecretsStatus.mockReturnValue(DEFAULT_STATUS_RETURN);
    vi.stubGlobal("fetch", vi.fn());
  });

  // 15-A-2：5 providers (google 已移除)
  it("renders 5 provider inputs — google field absent", () => {
    render(<SecretsSection />);
    const inputs = screen.getAllByTestId(/^secret-input-/);
    expect(inputs).toHaveLength(5);
    for (const input of inputs) {
      expect(input).toHaveAttribute("type", "password");
    }
    expect(screen.queryByTestId("secret-input-google")).not.toBeInTheDocument();
  });

  it("shows configured status (✓) for openai", () => {
    render(<SecretsSection />);
    expect(screen.getByText("✓")).toBeInTheDocument();
  });

  it("button label is 驗證並儲存", () => {
    render(<SecretsSection />);
    expect(screen.getByTestId("secrets-save-btn")).toHaveTextContent("驗證並儲存");
  });

  it("calls fetch POST /api/config/secrets/validate on save", async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce(
      mockFetchResponse({
        data: {
          results: { finmind: { status: "ok", message: "FinMind token 驗證成功" } },
          saved: ["finmind"],
        },
      }),
    );
    vi.stubGlobal("fetch", mockFetch);
    mockMutate.mockResolvedValueOnce(undefined);

    render(<SecretsSection />);
    fireEvent.change(screen.getByTestId("secret-input-finmind"), {
      target: { value: "fm-good-token" },
    });
    fireEvent.click(screen.getByTestId("secrets-save-btn"));

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/config/secrets/validate",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.finmind).toBe("fm-good-token");
  });

  it("shows success toast when saved count > 0", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        mockFetchResponse({
          data: {
            results: { finmind: { status: "ok", message: "ok" } },
            saved: ["finmind"],
          },
        }),
      ),
    );
    mockMutate.mockResolvedValueOnce(undefined);

    render(<SecretsSection />);
    fireEvent.change(screen.getByTestId("secret-input-finmind"), {
      target: { value: "fm-token" },
    });
    fireEvent.click(screen.getByTestId("secrets-save-btn"));

    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledTimes(1));
  });

  it("shows error toast when finmind fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        mockFetchResponse({
          data: {
            results: { finmind: { status: "invalid_key", message: "FinMind token 無效" } },
            saved: [],
          },
        }),
      ),
    );

    render(<SecretsSection />);
    fireEvent.change(screen.getByTestId("secret-input-finmind"), {
      target: { value: "bad-token" },
    });
    fireEvent.click(screen.getByTestId("secrets-save-btn"));

    await waitFor(() => expect(mockToastError).toHaveBeenCalledTimes(1));
  });

  it("shows error toast on HTTP 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        mockFetchResponse(
          { detail: { error: { message: "寫入設定檔失敗" } } },
          false,
          500,
        ),
      ),
    );

    render(<SecretsSection />);
    fireEvent.change(screen.getByTestId("secret-input-finmind"), {
      target: { value: "fm-token" },
    });
    fireEvent.click(screen.getByTestId("secrets-save-btn"));

    await waitFor(() => expect(mockToastError).toHaveBeenCalledTimes(1));
  });

  it("does not call fetch when all inputs are empty", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    render(<SecretsSection />);
    fireEvent.click(screen.getByTestId("secrets-save-btn"));
    await waitFor(() => expect(mockFetch).not.toHaveBeenCalled());
  });

  it("PROVIDERS 含 deepseek", () => {
    render(<SecretsSection />);
    expect(screen.getByTestId("secret-input-deepseek")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek API Key")).toBeInTheDocument();
  });

  it("SecretsStatus.deepseek 顯示 ✓", () => {
    mockUseSecretsStatus.mockReturnValue({
      status: { openai: false, anthropic: false, gemini: false, deepseek: true, finmind: false },
      isLoading: false,
      mutate: mockMutate,
    });
    render(<SecretsSection />);
    const checkmarks = screen.getAllByText("✓");
    expect(checkmarks).toHaveLength(1);
  });

  // 15-A-2：Google API Key 欄位不得出現
  it("15-A-2 regression: Google API Key 欄位不出現", () => {
    render(<SecretsSection />);
    expect(screen.queryByText("Google API Key")).not.toBeInTheDocument();
    expect(screen.queryByTestId("secret-input-google")).not.toBeInTheDocument();
  });
});
