// Tests for trading-calendar utilities (Phase 10-C-1)

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  businessDaysBetween,
  judgeStatus,
  latestTradeDate,
} from "@/lib/trading-calendar";

// 2026-05-14 is a Thursday
const FIXED_UTC = "2026-05-14T10:00:00Z"; // TW=18:00 Thu, US=06:00 Thu

describe("businessDaysBetween", () => {
  it("returns 0 when start equals end", () => {
    const d = new Date("2026-05-14");
    expect(businessDaysBetween(d, d)).toBe(0);
  });

  it("returns 0 when start is after end", () => {
    expect(businessDaysBetween(new Date("2026-05-14"), new Date("2026-05-13"))).toBe(0);
  });

  it("counts one weekday between adjacent days", () => {
    // Mon → Tue = 1
    expect(businessDaysBetween(new Date("2026-05-11"), new Date("2026-05-12"))).toBe(1);
  });

  it("skips Saturday and Sunday", () => {
    // Fri → Mon = 1 business day
    expect(businessDaysBetween(new Date("2026-05-08"), new Date("2026-05-11"))).toBe(1);
  });

  it("counts 5 weekdays in a full week", () => {
    // Mon → Fri next week excluding start = Mon→Mon = 5 (Tue+Wed+Thu+Fri+Mon)
    // Mon 2026-05-11 → Mon 2026-05-18 = 5 business days
    expect(businessDaysBetween(new Date("2026-05-11"), new Date("2026-05-18"))).toBe(5);
  });
});

describe("latestTradeDate", () => {
  afterEach(() => vi.useRealTimers());

  it("returns Thursday for TW market when today is Thursday", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC));
    const result = latestTradeDate("tw");
    expect(result.getUTCDay()).toBe(4); // 4 = Thursday
  });

  it("returns the same weekday for US market when not weekend", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC));
    const result = latestTradeDate("us");
    expect(result.getUTCDay()).toBe(4); // still Thursday in US
  });

  it("rolls back to Friday when Saturday in TW time", () => {
    vi.useFakeTimers();
    // Saturday UTC 2026-05-16 at TW midnight = still Saturday TW
    vi.setSystemTime(new Date("2026-05-16T02:00:00Z")); // TW=10:00 Sat
    const result = latestTradeDate("tw");
    expect(result.getUTCDay()).toBe(5); // Friday
  });
});

describe("judgeStatus", () => {
  afterEach(() => vi.useRealTimers());

  it("returns missing when available is false", () => {
    expect(judgeStatus("2026-05-14", false, "tw")).toBe("missing");
  });

  it("returns missing when endDate is null", () => {
    expect(judgeStatus(null, true, "tw")).toBe("missing");
  });

  it("returns missing when endDate is '-'", () => {
    expect(judgeStatus("-", true, "tw")).toBe("missing");
  });

  it("returns fresh when end_date equals latest trade date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC)); // TW latest = 2026-05-14
    expect(judgeStatus("2026-05-14", true, "tw")).toBe("fresh");
  });

  it("returns stale when 1 business day behind", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC)); // TW latest = 2026-05-14 (Thu)
    expect(judgeStatus("2026-05-13", true, "tw")).toBe("stale"); // Wed = 1 day behind
  });

  it("returns stale when 5 business days behind", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC)); // TW latest = 2026-05-14 (Thu)
    // 5 business days back from Thu = previous Thu = 2026-05-07
    expect(judgeStatus("2026-05-07", true, "tw")).toBe("stale");
  });

  it("returns missing when more than 5 business days behind", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_UTC)); // TW latest = 2026-05-14
    expect(judgeStatus("2026-04-30", true, "tw")).toBe("missing");
  });
});
