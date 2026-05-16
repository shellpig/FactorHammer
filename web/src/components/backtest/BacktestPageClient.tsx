"use client";

// Backtest page client — 4-tab framework (Phase 10-E-1)
// Tabs: 單次（active）/ 策略比較（disabled）/ 參數掃描（disabled）/ Walk-Forward（disabled）

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorBoundary } from "@/components/error-boundary";
import { SingleRunTab } from "./SingleRunTab";

type Tab = "single" | "batch" | "sweep" | "wfa";

const TABS: { id: Tab; label: string; phase?: string }[] = [
  { id: "single", label: "單次回測" },
  { id: "batch", label: "策略比較", phase: "10-E-2" },
  { id: "sweep", label: "參數掃描", phase: "10-E-3" },
  { id: "wfa", label: "Walk-Forward", phase: "10-E-4" },
];

function DisabledTabContent({ phase }: { phase: string }) {
  return (
    <div className="py-8 text-center text-sm text-slate-500">
      Phase {phase} 開發中，功能尚未開放。
    </div>
  );
}

export function BacktestPageClient() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<Tab>("single");

  useEffect(() => {
    const tabParam = searchParams.get("tab") as Tab | null;
    if (tabParam && TABS.some((t) => t.id === tabParam)) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  return (
    <div
      data-testid="backtest-page"
      className="mx-auto max-w-[2400px] space-y-4 p-4"
    >
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-700">
        {TABS.map((t) => {
          const isDisabled = !!t.phase;
          const isActive = t.id === activeTab && !isDisabled;

          if (isDisabled) {
            return (
              <div
                key={t.id}
                data-testid={`tab-${t.id}`}
                title={`Phase ${t.phase} 開發中`}
                className="relative flex cursor-not-allowed items-center gap-1.5 px-4 py-2 text-sm text-slate-600"
              >
                {t.label}
                <span className="rounded bg-slate-700 px-1 py-0.5 text-[10px] text-slate-500">
                  {t.phase} 開發中
                </span>
              </div>
            );
          }

          return (
            <button
              key={t.id}
              type="button"
              data-testid={`tab-${t.id}`}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 text-sm transition-colors ${
                isActive
                  ? "border-b-2 border-sky-500 text-sky-400"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <ErrorBoundary>
        {activeTab === "single" && <SingleRunTab />}
        {activeTab === "batch" && <DisabledTabContent phase="10-E-2" />}
        {activeTab === "sweep" && <DisabledTabContent phase="10-E-3" />}
        {activeTab === "wfa" && <DisabledTabContent phase="10-E-4" />}
      </ErrorBoundary>
    </div>
  );
}
