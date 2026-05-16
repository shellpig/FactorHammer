// Tests for use-backtest-job hook (Phase 10-E-1)

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useBacktestJob } from "@/hooks/use-backtest-job";

// Mock useToast
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

// Mock EventSource
class MockEventSource {
  url: string;
  static instances: MockEventSource[] = [];
  onerror: ((e: Event) => void) | null = null;
  listeners: Map<string, ((e: MessageEvent) => void)[]> = new Map();
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type)!.push(handler);
  }

  dispatchEvent(type: string, data: unknown) {
    const handlers = this.listeners.get(type) ?? [];
    for (const h of handlers) {
      h({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {
    this.readyState = 2;
  }
}

// Mock fetch
const mockFetch = vi.fn();

describe("useBacktestJob", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("fetch", mockFetch);
    mockToastSuccess.mockClear();
    mockToastError.mockClear();
    mockToastInfo.mockClear();
    mockFetch.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts in idle status", () => {
    const { result } = renderHook(() => useBacktestJob());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("transitions to running on start()", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "test-123" }),
    });

    const { result } = renderHook(() => useBacktestJob());
    act(() => {
      result.current.start("backtest_run", { symbol: "2330" });
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("running");
  });

  it("sets error status on HTTP failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: { error: { message: "Lock busy" } } }),
    });

    const { result } = renderHook(() => useBacktestJob());
    await act(async () => {
      await result.current.start("backtest_run", {});
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error?.code).toBe("HTTP_ERROR");
    expect(mockToastError).toHaveBeenCalledTimes(1);
  });

  it("creates EventSource after successful POST", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "job-abc" }),
    });

    const { result } = renderHook(() => useBacktestJob());
    await act(async () => {
      await result.current.start("backtest_run", { symbol: "2330" });
    });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain("/api/jobs/job-abc/events");
  });

  it("updates progress on SSE progress event", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "job-xyz" }),
    });

    const { result } = renderHook(() => useBacktestJob());
    await act(async () => {
      await result.current.start("backtest_run", {});
    });

    const es = MockEventSource.instances[0];
    act(() => {
      es.dispatchEvent("progress", { phase: "loading_data", status: "running" });
    });

    expect(result.current.progress?.phase).toBe("loading_data");
  });

  it("stores result on SSE result event", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "job-r" }),
    });

    const { result } = renderHook(() => useBacktestJob<{ symbol: string }>());
    await act(async () => {
      await result.current.start("backtest_run", {});
    });

    const es = MockEventSource.instances[0];
    act(() => {
      es.dispatchEvent("result", { symbol: "2330" });
    });

    expect(result.current.result?.symbol).toBe("2330");
  });

  it("calls cancel endpoint on cancel()", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: "job-cancel" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: { status: "cancelled" } }) });

    const { result } = renderHook(() => useBacktestJob());
    await act(async () => {
      await result.current.start("backtest_run", {});
    });

    await act(async () => {
      await result.current.cancel();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/cancel"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("resets to idle on reset()", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "job-reset" }),
    });

    const { result } = renderHook(() => useBacktestJob());
    await act(async () => {
      await result.current.start("backtest_run", {});
    });
    act(() => {
      result.current.reset();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
