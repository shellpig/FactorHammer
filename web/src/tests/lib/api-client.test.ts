// Tests for api-client (Phase 10-B)

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClientError, apiFetch } from "@/lib/api-client";

describe("ApiClientError", () => {
  it("is an instance of Error", () => {
    const err = new ApiClientError(404, "NOT_FOUND", "Not found");
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ApiClientError");
    expect(err.status).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.message).toBe("Not found");
  });

  it("falls back to HTTP status message when message is undefined", () => {
    const err = new ApiClientError(500, undefined, undefined);
    expect(err.message).toBe("HTTP 500");
  });
});

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("returns parsed JSON on success", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: { status: "ok" } }),
    } as Response);

    const result = await apiFetch<{ data: { status: string } }>("/api/health");
    expect(result).toEqual({ data: { status: "ok" } });
  });

  it("throws ApiClientError on non-ok response with error body", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        error: { code: "WHITELIST_REJECTED", message: "Key not allowed" },
      }),
    } as Response);

    await expect(apiFetch("/api/config")).rejects.toMatchObject({
      name: "ApiClientError",
      status: 422,
      code: "WHITELIST_REJECTED",
      message: "Key not allowed",
    });
  });

  it("throws ApiClientError when error body is unparseable", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => { throw new Error("JSON parse error"); },
    } as unknown as Response);

    const err = await apiFetch("/api/health").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiClientError);
    expect((err as ApiClientError).status).toBe(503);
  });

  it("reads error from FastAPI detail envelope (body.detail.error)", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        detail: { error: { code: "DELETE_PARTIAL", message: "刪除部分失敗：parquet: Permission denied" } },
      }),
    } as Response);

    await expect(apiFetch("/api/data/tw/2330")).rejects.toMatchObject({
      name: "ApiClientError",
      status: 500,
      code: "DELETE_PARTIAL",
      message: "刪除部分失敗：parquet: Permission denied",
    });
  });

  it("prefers detail.error over top-level error when both present", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({
        detail: { error: { code: "WRITE_LOCK_BUSY", message: "正在進行資料操作" } },
        error: { code: "OLD_CODE", message: "old message" },
      }),
    } as Response);

    await expect(apiFetch("/api/data/tw/2330")).rejects.toMatchObject({
      code: "WRITE_LOCK_BUSY",
      message: "正在進行資料操作",
    });
  });

  it("includes Content-Type header in requests", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response);

    await apiFetch("/api/health");

    const [, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    const headers = opts.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  // Phase 14-A: BASE_URL behavior tests
  it("api-client 預設走 same-origin（NEXT_PUBLIC_API_URL 未設時）", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response);

    await apiFetch("/api/data/symbols");

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    // NEXT_PUBLIC_API_URL not set in test env → BASE_URL = "" → relative same-origin path
    expect(url).toBe("/api/data/symbols");
  });

  it("api-client 接受 NEXT_PUBLIC_API_URL 覆蓋（escape hatch）", async () => {
    vi.resetModules();
    const prevUrl = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "http://100.64.0.1:8000";
    const { apiFetch: apiFetchEscaped } = await import("@/lib/api-client");

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response);

    await apiFetchEscaped("/api/data/symbols");

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://100.64.0.1:8000/api/data/symbols");

    if (prevUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = prevUrl;
    vi.resetModules();
  });
});
