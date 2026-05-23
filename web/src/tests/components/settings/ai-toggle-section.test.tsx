// Tests for AiToggleSection component (Phase 15-A-1 rewrite)

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
    info: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

const mockUpdateConfig = vi.fn();
const mockMutate = vi.fn();
vi.mock("swr", async (importOriginal) => {
  const mod = await importOriginal<typeof import("swr")>();
  return { ...mod, mutate: (...args: unknown[]) => mockMutate(...args) };
});

const mockUseConfig = vi.fn();
vi.mock("@/hooks/use-config", () => ({
  useConfig: (...args: unknown[]) => mockUseConfig(...args),
  updateConfig: (...args: unknown[]) => mockUpdateConfig(...args),
  CONFIG_SWR_KEY: "/api/config",
}));

import { AiToggleSection } from "@/components/settings/ai-toggle-section";

const DEFAULT_CONFIG_RETURN = {
  config: {
    ai: { enabled: false, provider: "anthropic", model: "claude-haiku-4-5-20251001" },
  },
  isLoading: false,
  mutate: vi.fn(),
};

describe("AiToggleSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseConfig.mockReturnValue(DEFAULT_CONFIG_RETURN);
  });

  it("renders section heading", () => {
    render(<AiToggleSection />);
    expect(screen.getByText("AI 分析")).toBeInTheDocument();
  });

  it("toggle is enabled (not disabled)", () => {
    render(<AiToggleSection />);
    const toggle = screen.getByTestId("ai-toggle");
    expect(toggle).not.toBeDisabled();
  });

  it("toggle reflects config (disabled = aria-checked false)", () => {
    render(<AiToggleSection />);
    expect(screen.getByTestId("ai-toggle")).toHaveAttribute("aria-checked", "false");
  });

  it("does not show 永久停用 label", () => {
    render(<AiToggleSection />);
    expect(screen.queryByText("（永久停用）")).not.toBeInTheDocument();
  });

  it("renders provider dropdown with 4 options", () => {
    render(<AiToggleSection />);
    const select = screen.getByTestId("ai-provider-select");
    const options = select.querySelectorAll("option");
    expect(options).toHaveLength(4);
    const values = Array.from(options).map((o) => o.value);
    expect(values).toContain("anthropic");
    expect(values).toContain("openai");
    expect(values).toContain("gemini");
    expect(values).toContain("deepseek");
  });

  it("model input renders with config model value", () => {
    render(<AiToggleSection />);
    const input = screen.getByTestId("ai-model-input");
    expect(input).toBeInTheDocument();
    expect((input as HTMLInputElement).value).toBe("claude-haiku-4-5-20251001");
  });

  it("clicking toggle flips aria-checked", () => {
    render(<AiToggleSection />);
    const toggle = screen.getByTestId("ai-toggle");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("changing provider auto-updates model to default", () => {
    render(<AiToggleSection />);
    fireEvent.change(screen.getByTestId("ai-provider-select"), {
      target: { value: "deepseek" },
    });
    expect((screen.getByTestId("ai-model-input") as HTMLInputElement).value).toBe(
      "deepseek-v4-flash",
    );
  });

  it("save button calls updateConfig with current state", async () => {
    mockUpdateConfig.mockResolvedValueOnce(undefined);
    mockMutate.mockResolvedValueOnce(undefined);

    render(<AiToggleSection />);
    fireEvent.click(screen.getByTestId("ai-save-btn"));

    await waitFor(() => expect(mockUpdateConfig).toHaveBeenCalledTimes(1));
    expect(mockUpdateConfig).toHaveBeenCalledWith({
      ai: { enabled: false, provider: "anthropic", model: "claude-haiku-4-5-20251001" },
    });
    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledWith("AI 設定已儲存"));
  });

  it("shows error toast when save fails", async () => {
    mockUpdateConfig.mockRejectedValueOnce(new Error("fail"));

    render(<AiToggleSection />);
    fireEvent.click(screen.getByTestId("ai-save-btn"));

    await waitFor(() => expect(mockToastError).toHaveBeenCalledTimes(1));
  });

  it("SWR config 載入後同步 local state", async () => {
    const configData = {
      ai: { enabled: true, provider: "deepseek", model: "deepseek-v4-flash" },
    };
    mockUseConfig.mockReturnValueOnce({ config: null, isLoading: true, mutate: vi.fn() });
    mockUseConfig.mockReturnValue({ config: configData, isLoading: false, mutate: vi.fn() });

    const { rerender } = render(<AiToggleSection />);
    rerender(<AiToggleSection />);

    await waitFor(() => {
      expect(screen.getByTestId("ai-toggle")).toHaveAttribute("aria-checked", "true");
    });
    expect((screen.getByTestId("ai-provider-select") as HTMLSelectElement).value).toBe("deepseek");
    expect((screen.getByTestId("ai-model-input") as HTMLInputElement).value).toBe(
      "deepseek-v4-flash",
    );
  });

  it("dirty 編輯中不被 SWR 覆寫", () => {
    const { rerender } = render(<AiToggleSection />);

    // User enables toggle → isDirty becomes true
    fireEvent.click(screen.getByTestId("ai-toggle"));
    expect(screen.getByTestId("ai-toggle")).toHaveAttribute("aria-checked", "true");

    // SWR revalidates with enabled=false — local state must remain true
    mockUseConfig.mockReturnValue({
      config: { ai: { enabled: false, provider: "anthropic", model: "claude-haiku-4-5-20251001" } },
      isLoading: false,
      mutate: vi.fn(),
    });
    rerender(<AiToggleSection />);

    expect(screen.getByTestId("ai-toggle")).toHaveAttribute("aria-checked", "true");
  });

  it("停用時 Provider / Model 欄位 disabled", () => {
    // Default mock: enabled=false → select and input must be disabled
    render(<AiToggleSection />);
    expect(screen.getByTestId("ai-provider-select")).toBeDisabled();
    expect(screen.getByTestId("ai-model-input")).toBeDisabled();

    // Enable toggle → fields become interactive
    fireEvent.click(screen.getByTestId("ai-toggle"));
    expect(screen.getByTestId("ai-provider-select")).not.toBeDisabled();
    expect(screen.getByTestId("ai-model-input")).not.toBeDisabled();
  });
});
