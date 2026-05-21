// Number, date, and currency formatters (Phase 10-B)

import type { Market } from "@/types/market";
import { MARKET_CURRENCY } from "@/types/market";

/** Format a number as currency string (e.g. "TWD 1,234.56"). */
export function formatCurrency(
  value: number,
  market: Market,
  decimals = 2,
): string {
  const currency = MARKET_CURRENCY[market];
  return `${currency} ${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/** Format a plain number with thousands separator. */
export function formatNumber(value: number, decimals = 2): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format percentage with sign (e.g. "+3.45%" or "-1.23%"). */
export function formatPct(value: number, decimals = 2): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/** Format volume as abbreviated string (e.g. 1234567 → "1.23M"). */
export function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString("en-US");
}

/** Format TW daily volume with share semantics (e.g. 2_379_159 -> "238萬股"). */
export function formatTwDailyVolume(value: number): string {
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}億股`;
  if (value >= 10_000) return `${Math.round(value / 10_000).toLocaleString("en-US")}萬股`;
  return `${Math.round(value).toLocaleString("en-US")}股`;
}

/** Format an ISO date string to "YYYY-MM-DD". */
export function formatDate(isoString: string): string {
  return isoString.slice(0, 10);
}

/** Return colour class based on positive/negative/zero value. */
export function changeColor(
  value: number,
  market: Market,
): "text-rise" | "text-fall" | "text-neutral" {
  if (value === 0) return "text-neutral";
  const isPositive = value > 0;
  // TW: red=up, green=down; US: green=up, red=down
  if (market === "tw") {
    return isPositive ? "text-rise" : "text-fall";
  }
  return isPositive ? "text-fall" : "text-rise";
}
