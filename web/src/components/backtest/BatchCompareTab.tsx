"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { useBacktestJob } from "@/hooks/use-backtest-job";
import { useToast } from "@/hooks/use-toast";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/skeletons";
import { MarketSwitcher } from "@/components/market-switcher";
import { StockSelector } from "@/components/stock-selector";
import type { Market } from "@/types/market";
import { BacktestProgressBar } from "./BacktestProgressBar";
import { DateRangePicker } from "./DateRangePicker";
import { StrategyMultiSelect } from "./StrategyMultiSelect";
import { MultiEquityChart } from "./MultiEquityChart";
import { ComparisonTable } from "./ComparisonTable";
import { TearsheetCards } from "./TearsheetCards";
import { CandleChartWithMarkers } from "./CandleChartWithMarkers";
import { EquityCurveChart } from "./EquityCurveChart";
import { TradesTable } from "./TradesTable";
import type { BacktestBatchResult, BacktestBatchSummary } from "./batch-types";

interface StrategyPreset {
  name: string;
  type: string;
  params: Record<string, number | string | boolean>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) {
      throw new Error(`HTTP ${r.status}`);
    }
    return r.json();
  }).then((body) => body.data as StrategyPreset[]);

function inferMaOverlay(
  strategyType: string,
  params: Record<string, number | string | boolean>,
): Array<{ name: string; period: number; color: string }> {
  const toNum = (v: unknown, d: number) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : d;
  };

  if (strategyType === "moving_average_cross") {
    const shortWindow = toNum(params.short_window, 20);
    const longWindow = toNum(params.long_window, 60);
    return [
      { name: `MA${shortWindow}`, period: shortWindow, color: "#60a5fa" },
      { name: `MA${longWindow}`, period: longWindow, color: "#f59e0b" },
    ];
  }
  if (strategyType === "bollinger_band") {
    const period = toNum(params.period, 20);
    return [{ name: `MA${period}`, period, color: "#60a5fa" }];
  }
  if (strategyType === "bias") {
    const period = toNum(params.ma_period, 20);
    return [{ name: `MA${period}`, period, color: "#60a5fa" }];
  }
  return [];
}

function parseFilename(disposition: string | null): string {
  if (!disposition) return "batch_result.csv";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  if (!match || !match[1]) return "batch_result.csv";
  return match[1];
}

export function BatchCompareTab() {
  const toast = useToast();
  const [market, setMarket] = useState<Market>("tw");
  const [symbol, setSymbol] = useState("");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2026-04-30");
  const [initialCapital, setInitialCapital] = useState(1_000_000);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [expandedPresetIndex, setExpandedPresetIndex] = useState<number | null>(null);
  const [sawProgress, setSawProgress] = useState(false);

  const { data: presets = [], isLoading: presetsLoading } = useSWR<StrategyPreset[]>(
    `${API_BASE}/api/config/strategies`,
    fetcher,
  );

  useEffect(() => {
    if (presets.length > 0 && selectedIndices.length === 0) {
      setSelectedIndices(presets.map((_, i) => i));
    }
  }, [presets, selectedIndices.length]);

  const {
    jobId,
    status,
    progress,
    result,
    error,
    start,
    cancel,
    reset,
  } = useBacktestJob<BacktestBatchResult>({
    disableDefaultToasts: true,
    onProgress: () => setSawProgress(true),
    onComplete: (payload) => {
      if (!payload) {
        toast.success("比較完成");
        return;
      }
      toast.success(`比較完成（${payload.success_count} 成功 / ${payload.failed_count} 失敗）`);
    },
    onCancelled: (payload) => {
      if (!payload) {
        toast.info("比較已取消");
        return;
      }
      toast.info(`比較已取消（已完成 ${payload.completed_presets}/${payload.total_presets}）`);
    },
    onError: (err) => {
      toast.error(`比較失敗：${err.message}`);
    },
  });

  const isRunning = status === "running";

  const summaries = result?.summaries ?? [];
  const successfulSummaries = useMemo(
    () => summaries.filter((s) => !s.error && s.detail),
    [summaries],
  );

  const handleMarketChange = useCallback((nextMarket: Market) => {
    setMarket(nextMarket);
    setSymbol("");
    setExpandedPresetIndex(null);
    setSawProgress(false);
    reset();
  }, [reset]);

  const handleStart = useCallback(async () => {
    if (!symbol || selectedIndices.length === 0) return;
    setExpandedPresetIndex(null);
    setSawProgress(false);
    await start("backtest_batch", {
      market,
      symbol,
      start_date: startDate,
      end_date: endDate,
      initial_capital: initialCapital,
      strategy_preset_indices: selectedIndices,
    });
  }, [start, market, symbol, startDate, endDate, initialCapital, selectedIndices]);

  const handleDownloadCsv = useCallback(async () => {
    if (!jobId || !result) return;
    try {
      const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/result?format=csv`);
      if (!resp.ok) {
        toast.error(`下載失敗：HTTP ${resp.status}`);
        return;
      }
      const blob = await resp.blob();
      const filename = parseFilename(resp.headers.get("content-disposition"));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.success(`已下載：${filename}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`下載失敗：${msg}`);
    }
  }, [jobId, result, toast]);

  function renderExpanded(summary: BacktestBatchSummary) {
    if (!summary.detail || !result) return null;
    const detail = summary.detail;
    const maOverlay = inferMaOverlay(summary.strategy_type, summary.strategy_params);

    return (
      <div data-testid="batch-row-expanded" className="space-y-3">
        {detail.metrics && (
          <TearsheetCards
            metrics={detail.metrics}
            currency={detail.currency}
            isDca={summary.strategy_type === "dollar_cost_averaging"}
          />
        )}
        <CandleChartWithMarkers
          priceData={result.price_data}
          signals={detail.signals}
          market={result.market}
          maOverlay={maOverlay}
          height={360}
        />
        <EquityCurveChart
          series={[{ name: `${summary.preset_name} 資金曲線`, data: detail.equity_curve, color: "#60a5fa" }]}
          height={200}
        />
        {detail.trades.length > 0 ? (
          <TradesTable trades={detail.trades} currency={detail.currency} />
        ) : (
          <div className="rounded border border-slate-700 p-3 text-xs text-slate-400">此策略無交易紀錄。</div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-lg border border-slate-700 bg-slate-800/40 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">市場</label>
            <MarketSwitcher value={market} onChange={handleMarketChange} />
          </div>

          <div className="flex min-w-[240px] flex-col gap-1">
            <label className="text-xs text-slate-400">股票代碼</label>
            <StockSelector market={market} value={symbol} onChange={setSymbol} />
          </div>

          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartChange={setStartDate}
            onEndChange={setEndDate}
            disabled={isRunning}
          />

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">初始資金</label>
            <input
              type="number"
              data-testid="batch-initial-capital-input"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              disabled={isRunning}
              className="w-32 rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
            />
          </div>

          <button
            type="button"
            data-testid="start-batch-btn"
            disabled={isRunning || !symbol || selectedIndices.length === 0 || presetsLoading}
            onClick={handleStart}
            className="rounded bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            開始比較
          </button>

          <button
            type="button"
            data-testid="download-batch-csv-btn"
            disabled={!result}
            onClick={handleDownloadCsv}
            className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
          >
            匯出 CSV
          </button>
        </div>

        <StrategyMultiSelect
          presets={presets}
          selectedIndices={selectedIndices}
          onChange={setSelectedIndices}
          disabled={isRunning || presetsLoading}
        />
      </div>

      {status === "idle" && (
        <p className="text-sm text-slate-400">選擇策略後按「開始比較」</p>
      )}

      {status === "running" && (
        <>
          <BacktestProgressBar
            current={progress?.current}
            total={progress?.total}
            phase="running"
            onCancel={cancel}
          />
          {!sawProgress ? (
            <>
              <ChartSkeleton height={260} />
              <TableSkeleton rows={8} columns={10} />
            </>
          ) : (
            <p className="text-sm text-slate-400">比較執行中，等待結果彙整…</p>
          )}
        </>
      )}

      {(status === "complete" || status === "cancelled") && result && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              成功：{result.success_count}
            </div>
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              失敗：{result.failed_count}
            </div>
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              已完成：{result.completed_presets}/{result.total_presets}
            </div>
          </div>

          <MultiEquityChart summaries={successfulSummaries} />

          <ComparisonTable
            summaries={result.summaries}
            expandedPresetIndex={expandedPresetIndex}
            onToggleExpand={(presetIndex) => {
              setExpandedPresetIndex((prev) => (prev === presetIndex ? null : presetIndex));
            }}
            renderExpanded={renderExpanded}
          />

          {status === "cancelled" && (
            <p className="text-xs text-slate-500">（比較已取消，顯示取消前已完成的策略結果）</p>
          )}
        </div>
      )}

      {status === "error" && error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-rose-300">
          <p className="font-semibold">執行失敗</p>
          <p className="mt-1 text-sm">
            {error.message}（代碼：{error.code}）
          </p>
        </div>
      )}
    </div>
  );
}
