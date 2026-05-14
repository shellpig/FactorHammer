// SWR hook for data management list (Phase 10-C-1)
// Fetches symbol list + per-symbol status, combines into SymbolRow[].

import useSWR from "swr";
import { apiFetch } from "@/lib/api-client";
import type { SymbolRow, SymbolStatusRaw, SymbolStatusResponse, SymbolsListResponse } from "@/types/data";
import { judgeStatus } from "@/lib/trading-calendar";
import type { TradingMarket } from "@/lib/trading-calendar";

async function fetchDataList(market: TradingMarket): Promise<SymbolRow[]> {
  const listResp = await apiFetch<SymbolsListResponse>(`/api/data/symbols?market=${market}`);

  // list_symbols returns dict records; extract the symbol field
  const symbols: string[] = listResp.data.map((row) =>
    typeof row === "string" ? row : (row as { symbol: string }).symbol,
  );

  if (symbols.length === 0) return [];

  const rows = await Promise.all(
    symbols.map(async (symbol): Promise<SymbolRow> => {
      let statuses: SymbolStatusRaw[] = [];
      try {
        const statusResp = await apiFetch<SymbolStatusResponse>(
          `/api/data/status/${market}/${symbol}`,
        );
        statuses = statusResp.data;
      } catch {
        // Symbol status unavailable — treat as missing
      }

      const rawDaily = statuses.find((s) => s.data_type === "raw_daily");
      const adjDaily = statuses.find((s) => s.data_type === "adjusted_daily");

      const available = rawDaily?.available ?? false;
      const endDate = rawDaily?.end_date ?? null;
      const startDate = rawDaily?.start_date ?? null;
      const bars = rawDaily?.row_count ?? 0;
      const hasAdjusted = adjDaily?.available ?? false;

      return {
        symbol,
        market,
        firstDate: startDate && startDate !== "-" ? startDate : null,
        lastDate: endDate && endDate !== "-" ? endDate : null,
        bars,
        status: judgeStatus(endDate ?? null, available, market),
        hasAdjusted,
      };
    }),
  );

  return rows;
}

export function useDataList(market: TradingMarket) {
  const { data, error, isLoading, mutate } = useSWR(
    ["/api/data/list", market],
    () => fetchDataList(market),
    { refreshInterval: 0, revalidateOnFocus: false },
  );

  return {
    rows: data ?? [],
    isLoading,
    error: error as Error | undefined,
    mutate,
  };
}
