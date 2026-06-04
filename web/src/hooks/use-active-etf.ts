"use client";

import useSWR from "swr";
import { apiFetch } from "@/lib/api-client";
import type { ActiveEtf, ActiveEtfHoldingsResponse } from "@/types/active-etf";

export function useActiveEtfList() {
  const { data, error, isLoading, mutate } = useSWR<ActiveEtf[]>(
    "/api/active-etf/list",
    async (url: string) => {
      const res = await apiFetch<{ etfs: ActiveEtf[] }>(url);
      return res.etfs;
    },
  );
  return { etfs: data ?? [], isLoading, isError: !!error, error, mutate };
}

export function useActiveEtfHoldings(code: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ActiveEtfHoldingsResponse | null>(
    code ? `/api/active-etf/${code}/holdings` : null,
    async (url: string) => {
      const res = await apiFetch<ActiveEtfHoldingsResponse>(url);
      return res;
    },
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    }
  );
  return { holdings: data ?? null, isLoading, isError: !!error, error, mutate };
}
