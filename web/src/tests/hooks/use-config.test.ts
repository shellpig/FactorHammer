// Tests for use-config hook (Phase 10-G-2)

import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { SWRConfig } from "swr";

// Hoist mocks so vi.mock factories can reference them
const { mockApiFetch, mockApiPut, mockApiPost, mockApiDeleteNoContent, mockSWRMutate } =
  vi.hoisted(() => ({
    mockApiFetch: vi.fn(),
    mockApiPut: vi.fn(),
    mockApiPost: vi.fn(),
    mockApiDeleteNoContent: vi.fn(),
    mockSWRMutate: vi.fn().mockResolvedValue(undefined),
  }));

// Mock SWR — replace global mutate with spy, keep everything else real
vi.mock("swr", async (importOriginal) => {
  const actual = await importOriginal<typeof import("swr")>();
  return {
    ...actual,
    mutate: (...args: unknown[]) => mockSWRMutate(...args),
  };
});

vi.mock("@/lib/api-client", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  apiPut: (...args: unknown[]) => mockApiPut(...args),
  apiPost: (...args: unknown[]) => mockApiPost(...args),
  apiDeleteNoContent: (...args: unknown[]) => mockApiDeleteNoContent(...args),
  ApiClientError: class ApiClientError extends Error {
    constructor(
      public status: number,
      public code: string | undefined,
      message: string | undefined,
    ) {
      super(message);
    }
  },
}));

import {
  useConfig,
  updateConfig,
  useSecretsStatus,
  useStrategyPresets,
  updateSecrets,
  upsertStrategyPreset,
  deleteStrategyPreset,
  restoreStrategyDefaults,
} from "@/hooks/use-config";

// Fresh SWR cache per test — prevents deduplication across tests
function freshWrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(
    SWRConfig,
    { value: { provider: () => new Map() } },
    children,
  );
}

describe("useConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("SWR fetches /api/config and returns config data", async () => {
    const mockConfig = {
      ai: { enabled: true, provider: "deepseek", model: "deepseek-v4-flash" },
      ui: { theme: "dark", use_extras: true },
      risk: {},
      backtest: {},
      strategies: [],
    };
    mockApiFetch.mockResolvedValueOnce({ data: mockConfig });

    const { result } = renderHook(() => useConfig(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/config");
    expect(result.current.config?.ai.provider).toBe("deepseek");
  });

  it("returns null config on error", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("network error"));

    const { result } = renderHook(() => useConfig(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.config).toBeNull();
  });
});

describe("updateConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("PUT /api/config with { patch: ... } body shape", async () => {
    mockApiPut.mockResolvedValueOnce({ data: {}, meta: {} });

    await updateConfig({ ai: { enabled: true, provider: "deepseek", model: "deepseek-v4-flash" } });

    expect(mockApiPut).toHaveBeenCalledWith("/api/config", {
      patch: { ai: { enabled: true, provider: "deepseek", model: "deepseek-v4-flash" } },
    });
  });

  it("成功後觸發 mutate(CONFIG_SWR_KEY)", async () => {
    mockApiPut.mockResolvedValueOnce({ data: {}, meta: {} });

    await updateConfig({ ai: { enabled: true } });

    expect(mockSWRMutate).toHaveBeenCalledWith("/api/config");
  });

  it("rejects when apiPut fails", async () => {
    mockApiPut.mockRejectedValueOnce(new Error("server error"));

    await expect(updateConfig({ ai: { enabled: true } })).rejects.toThrow("server error");
  });
});

describe("useSecretsStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns status from API", async () => {
    mockApiFetch.mockResolvedValueOnce({
      data: { openai: true, anthropic: false, gemini: false, finmind: false, google: false },
    });

    const { result } = renderHook(() => useSecretsStatus(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.status.openai).toBe(true);
    expect(result.current.status.anthropic).toBe(false);
  });

  it("defaults to empty object on error", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("network error"));

    const { result } = renderHook(() => useSecretsStatus(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.status).toEqual({});
  });
});

describe("useStrategyPresets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns presets from API", async () => {
    mockApiFetch.mockResolvedValueOnce({
      data: [{ name: "MA Cross", type: "moving_average_cross", params: { short_window: 20, long_window: 60 }, market: "tw" }],
    });

    const { result } = renderHook(() => useStrategyPresets(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.presets).toHaveLength(1);
    expect(result.current.presets[0].name).toBe("MA Cross");
    expect(result.current.presets[0].market).toBe("tw");
  });

  it("defaults to empty array on error", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("network error"));

    const { result } = renderHook(() => useStrategyPresets(), { wrapper: freshWrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.presets).toEqual([]);
  });
});

describe("updateSecrets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls apiPut with correct path and payload", async () => {
    mockApiPut.mockResolvedValueOnce({ data: { updated: true }, meta: {} });

    await updateSecrets({ openai: "sk-test" });

    expect(mockApiPut).toHaveBeenCalledWith("/api/config/secrets", { keys: { openai: "sk-test" } });
  });
});

describe("upsertStrategyPreset", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls apiPost with preset and returns name", async () => {
    mockApiPost.mockResolvedValueOnce({ data: { upserted: true, name: "TestMA" }, meta: {} });

    const result = await upsertStrategyPreset({
      name: "TestMA",
      type: "moving_average_cross",
      params: { short_window: 20, long_window: 60 },
      market: "us",
    });

    expect(result.name).toBe("TestMA");
    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/config/strategies",
      expect.objectContaining({
        preset: expect.objectContaining({ name: "TestMA", market: "us" }),
      }),
    );
  });
});

describe("deleteStrategyPreset", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls apiDeleteNoContent with encoded name", async () => {
    mockApiDeleteNoContent.mockResolvedValueOnce(undefined);

    await deleteStrategyPreset("MA Cross");

    expect(mockApiDeleteNoContent).toHaveBeenCalledWith(
      "/api/config/strategies/MA%20Cross",
    );
  });
});

describe("restoreStrategyDefaults", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls restore endpoint and returns count", async () => {
    mockApiPost.mockResolvedValueOnce({ data: { count: 8 }, meta: {} });

    const count = await restoreStrategyDefaults();

    expect(count).toBe(8);
    expect(mockApiPost).toHaveBeenCalledWith("/api/config/strategies/restore", {});
  });
});
