"use client";

import useSWR from "swr";
import { apiGet } from "@/lib/api-client";
import type { DashboardPayloadResponse } from "@/types/analysis";
import type { Market } from "@/types/market";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_DASHBOARD === "1";

async function fetchDashboardMock(
  symbol: string,
): Promise<DashboardPayloadResponse> {
  const target = `/mock/dashboard_${symbol.toLowerCase()}.json`;
  const fallback = "/mock/dashboard_2330.json";
  const res = await fetch(target);
  if (res.ok) {
    return res.json() as Promise<DashboardPayloadResponse>;
  }
  const fallbackRes = await fetch(fallback);
  if (!fallbackRes.ok) {
    throw new Error("mock dashboard payload not found");
  }
  return fallbackRes.json() as Promise<DashboardPayloadResponse>;
}

export function useDashboard(symbol: string | null, market: Market) {
  const key = symbol ? `dashboard/${market}/${symbol}` : null;

  return useSWR<DashboardPayloadResponse>(
    key,
    async () => {
      if (USE_MOCK) {
        return fetchDashboardMock(symbol ?? "2330");
      }
      const encodedSymbol = encodeURIComponent(symbol ?? "");
      const endpoint = `/api/dashboard/payload?symbol=${encodedSymbol}&market=${market}`;
      const response = await apiGet<DashboardPayloadResponse>(endpoint);
      return response.data;
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
    },
  );
}
