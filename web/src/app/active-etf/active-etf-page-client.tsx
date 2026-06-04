"use client";

import { useEffect, useState } from "react";
import { useActiveEtfList, useActiveEtfHoldings } from "@/hooks/use-active-etf";
import { EtfSelector } from "@/components/active-etf/etf-selector";
import { BuySellPanel } from "@/components/active-etf/buy-sell-panel";
import { HoldingsTable } from "@/components/active-etf/holdings-table";
import { TableSkeleton } from "@/components/skeletons";
import { FileText, AlertTriangle } from "lucide-react";

const LOCAL_STORAGE_KEY = "qt-last-active-etf";

export function ActiveEtfPageClient() {
  const { etfs, isLoading: isListLoading, isError: isListError } = useActiveEtfList();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

  // Initialize selected code from localStorage or first item
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved && /^\d{5}A$/.test(saved)) {
        setSelectedCode(saved);
      } else if (etfs.length > 0) {
        setSelectedCode(etfs[0].code);
      }
    }
  }, [etfs]);

  // Handle selected ETF change
  const handleSelectEtf = (code: string) => {
    setSelectedCode(code || null);
    if (code) {
      localStorage.setItem(LOCAL_STORAGE_KEY, code);
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    }
  };

  const {
    holdings: data,
    isLoading: isHoldingsLoading,
    isError: isHoldingsError,
    error: holdingsError,
    mutate: refetchHoldings,
  } = useActiveEtfHoldings(selectedCode);

  const selectedEtfInfo = etfs.find((e) => e.code === selectedCode);
  const etfDisplayName = selectedEtfInfo
    ? `${selectedEtfInfo.code} ${selectedEtfInfo.name}`
    : selectedCode || "";

  return (
    <div className="space-y-6 pb-16">
      {/* ── Header ── */}
      <div className="flex flex-col gap-4 border-b border-border pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FileText className="h-6 w-6 text-primary" />
            主動式 ETF 持股追蹤
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            追蹤每日持股明細、權重變動及增減差異 (MoneyDJ 資料源)
          </p>
        </div>

        {/* Dropdown Selector */}
        <EtfSelector
          etfs={etfs}
          selectedCode={selectedCode}
          onSelectEtf={handleSelectEtf}
          isListLoading={isListLoading}
          isListError={isListError}
          isHoldingsLoading={isHoldingsLoading}
          onRefresh={refetchHoldings}
        />
      </div>

      {/* ── Main Dashboard Panels ── */}
      {!selectedCode ? (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
          <h3 className="mt-4 text-lg font-semibold text-foreground">未選擇 ETF</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            請於右上角下拉選單選擇一檔主動式 ETF 以查看持股與變動分析。
          </p>
        </div>
      ) : isHoldingsLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-lg border border-border p-4 space-y-4">
              <div className="h-6 w-32 bg-muted animate-pulse rounded" />
              <TableSkeleton rows={4} columns={3} />
            </div>
            <div className="rounded-lg border border-border p-4 space-y-4">
              <div className="h-6 w-32 bg-muted animate-pulse rounded" />
              <TableSkeleton rows={4} columns={3} />
            </div>
          </div>
          <div className="rounded-lg border border-border p-4 space-y-4">
            <div className="h-6 w-32 bg-muted animate-pulse rounded" />
            <TableSkeleton rows={8} columns={5} />
          </div>
        </div>
      ) : isHoldingsError ? (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-6 text-center space-y-3">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
          <h3 className="text-lg font-semibold text-foreground">載入資料失敗</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            {holdingsError?.message || "無法從 MoneyDJ 擷取持股資料，請稍後重試。"}
          </p>
          <button
            onClick={() => refetchHoldings()}
            className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus:outline-none"
          >
            重試
          </button>
        </div>
      ) : (
        <div className="space-y-6" data-testid="active-etf-content">
          {/* ETF Title Badge */}
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-0.5 text-sm font-semibold text-primary">
              {etfDisplayName}
            </span>
            <span className="text-xs text-muted-foreground">
              資料日期：{data?.latest_date || "無"}
            </span>
          </div>

          <div
            className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(320px,0.88fr)_minmax(560px,1.12fr)] xl:items-start"
            data-testid="active-etf-panel-grid"
          >
            {/* ── Panel 1: 持股變動 ── */}
            <BuySellPanel data={data} />

            {/* ── Panel 2: 目前總體持股 ── */}
            <HoldingsTable data={data} />
          </div>
        </div>
      )}
    </div>
  );
}
