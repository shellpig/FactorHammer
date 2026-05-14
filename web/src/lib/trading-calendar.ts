// Trading calendar utilities — used for status badge judgement (Phase 10-C-1)

export type TradingMarket = "tw" | "us";

// Return the most recent trading day for the given market.
// Uses simple UTC-offset approximation; ignores public holidays.
export function latestTradeDate(market: TradingMarket): Date {
  const now = new Date();
  // TW = UTC+8, US Eastern ≈ UTC-4 (EDT, close enough for this purpose)
  const offsetHours = market === "tw" ? 8 : -4;
  const localMs = now.getTime() + offsetHours * 3600 * 1000;
  const localDate = new Date(localMs);

  // Roll back to last weekday if today is weekend
  const dayOfWeek = localDate.getUTCDay(); // 0=Sun, 6=Sat
  const rollback = dayOfWeek === 0 ? 2 : dayOfWeek === 6 ? 1 : 0;
  localDate.setUTCDate(localDate.getUTCDate() - rollback);

  return localDate;
}

// Count business days strictly between start (exclusive) and end (inclusive).
// Returns 0 when start >= end.
export function businessDaysBetween(start: Date, end: Date): number {
  if (start >= end) return 0;
  let count = 0;
  const cur = new Date(start);
  cur.setUTCDate(cur.getUTCDate() + 1);
  while (cur <= end) {
    const day = cur.getUTCDay();
    if (day !== 0 && day !== 6) count++;
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return count;
}

export function judgeStatus(
  endDate: string | null,
  available: boolean,
  market: TradingMarket,
): "fresh" | "stale" | "missing" {
  if (!available || !endDate || endDate === "-") return "missing";
  const end = new Date(endDate);
  const latest = latestTradeDate(market);
  // Normalise both to UTC midnight for day-level comparison
  latest.setUTCHours(0, 0, 0, 0);
  end.setUTCHours(0, 0, 0, 0);
  const days = businessDaysBetween(end, latest);
  if (days === 0) return "fresh";
  if (days <= 5) return "stale";
  return "missing";
}
