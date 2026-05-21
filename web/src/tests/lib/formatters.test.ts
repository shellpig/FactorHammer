// Tests for lib/formatters (Phase 10-B)

import { describe, it, expect } from "vitest";
import {
  formatCurrency,
  formatNumber,
  formatPct,
  formatVolume,
  formatTwDailyVolume,
  formatDate,
  changeColor,
} from "@/lib/formatters";

describe("formatCurrency", () => {
  it("formats TWD correctly", () => {
    expect(formatCurrency(1234.56, "tw")).toBe("TWD 1,234.56");
  });

  it("formats USD correctly", () => {
    expect(formatCurrency(9876.54, "us")).toBe("USD 9,876.54");
  });
});

describe("formatNumber", () => {
  it("formats with 2 decimals by default", () => {
    expect(formatNumber(1000)).toBe("1,000.00");
  });

  it("respects custom decimals", () => {
    expect(formatNumber(1234.5678, 4)).toBe("1,234.5678");
  });
});

describe("formatPct", () => {
  it("shows + sign for positive", () => {
    expect(formatPct(3.45)).toBe("+3.45%");
  });

  it("shows - sign for negative", () => {
    expect(formatPct(-1.23)).toBe("-1.23%");
  });

  it("shows + for zero", () => {
    expect(formatPct(0)).toBe("+0.00%");
  });
});

describe("formatVolume", () => {
  it("abbreviates millions", () => {
    expect(formatVolume(1_234_567)).toBe("1.23M");
  });

  it("abbreviates thousands", () => {
    expect(formatVolume(9_500)).toBe("9.5K");
  });

  it("shows raw number for small values", () => {
    expect(formatVolume(999)).toBe("999");
  });
});

describe("formatTwDailyVolume", () => {
  it("formats millions in 萬股", () => {
    expect(formatTwDailyVolume(2_379_159)).toBe("238萬股");
  });

  it("formats hundred-millions in 億股", () => {
    expect(formatTwDailyVolume(123_000_000)).toBe("1.2億股");
  });

  it("formats small numbers in 股", () => {
    expect(formatTwDailyVolume(999)).toBe("999股");
  });
});

describe("formatDate", () => {
  it("extracts YYYY-MM-DD from ISO string", () => {
    expect(formatDate("2026-05-14T10:30:00+08:00")).toBe("2026-05-14");
  });
});

describe("changeColor", () => {
  it("TW positive → text-rise (red)", () => {
    expect(changeColor(5, "tw")).toBe("text-rise");
  });

  it("TW negative → text-fall (green)", () => {
    expect(changeColor(-3, "tw")).toBe("text-fall");
  });

  it("US positive → text-fall (green in US context)", () => {
    // US convention: positive = green = fall color token (inverted naming)
    expect(changeColor(5, "us")).toBe("text-fall");
  });

  it("US negative → text-rise (red in US context)", () => {
    expect(changeColor(-5, "us")).toBe("text-rise");
  });

  it("zero → text-neutral", () => {
    expect(changeColor(0, "tw")).toBe("text-neutral");
    expect(changeColor(0, "us")).toBe("text-neutral");
  });
});
