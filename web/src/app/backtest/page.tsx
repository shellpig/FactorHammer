// Backtest research page — 4-tab framework (Phase 10-E-1)

import type { Metadata } from "next";
import { Suspense } from "react";
import { BacktestPageClient } from "@/components/backtest/BacktestPageClient";

export const metadata: Metadata = {
  title: "回測研究 | FactorHammer",
  description: "策略回測、參數掃描與 Walk-Forward 分析。",
};

export default function BacktestPage() {
  return (
    <Suspense>
      <BacktestPageClient />
    </Suspense>
  );
}
