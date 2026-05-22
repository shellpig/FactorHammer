"use client";

import { useCallback, useMemo, useState } from "react";
import { useBacktestJob } from "@/hooks/use-backtest-job";
import { useToast } from "@/hooks/use-toast";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/skeletons";
import type { Market } from "@/types/market";
import { BacktestProgressBar } from "./BacktestProgressBar";
import { ParamGridForm } from "./ParamGridForm";
import { SweepRankingTable } from "./SweepRankingTable";
import { SweepHeatmap } from "./SweepHeatmap";
import { MAX_SWEEP_COMBOS, SWEEP_DEFAULTS } from "./sweep-constants";
import type { BacktestSweepResult, SweepStrategyType } from "./sweep-types";
import { createDefaultParamInputs, type SweepStartPayload } from "./sweep-helpers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function parseFilename(disposition: string | null): string {
  if (!disposition) return "sweep_result.csv";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  if (!match || !match[1]) return "sweep_result.csv";
  return match[1];
}

function paramsToText(params: Record<string, number>): string {
  return Object.entries(params)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join(", ");
}

export function SweepTab() {
  const toast = useToast();
  const [market, setMarket] = useState<Market>("tw");
  const [symbol, setSymbol] = useState("");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2026-04-30");
  const [strategyType, setStrategyType] = useState<SweepStrategyType>("moving_average_cross");
  const [paramInputs, setParamInputs] = useState<Record<string, string>>(createDefaultParamInputs("moving_average_cross"));
  const [initialCapital, setInitialCapital] = useState(1_000_000);
  const [sawProgress, setSawProgress] = useState(false);

  const {
    jobId,
    status,
    progress,
    result,
    error,
    start,
    cancel,
    reset,
  } = useBacktestJob<BacktestSweepResult>({
    disableDefaultToasts: true,
    onProgress: () => setSawProgress(true),
    onComplete: (payload) => {
      if (!payload) {
        toast.success("掃描完成");
        return;
      }
      toast.success(`掃描完成，共 ${payload.valid_combos} 個合法組合`);
    },
    onCancelled: (payload) => {
      if (!payload) {
        toast.info("掃描已取消");
        return;
      }
      toast.info(`掃描已取消（已完成 ${payload.results.length}/${payload.valid_combos}）`);
    },
    onError: (err) => {
      toast.error(`掃描失敗：${err.message}`);
    },
  });

  const isRunning = status === "running";
  const heatmapEnabled = useMemo(() => {
    if (!result || result.results.length === 0) return false;
    const first = result.results[0];
    return Object.keys(first.params).length === 2;
  }, [result]);

  const handleMarketChange = useCallback((nextMarket: Market) => {
    setMarket(nextMarket);
    setSymbol("");
    setSawProgress(false);
    reset();
  }, [reset]);

  const handleStrategyTypeChange = useCallback((nextType: SweepStrategyType) => {
    setStrategyType(nextType);
    setParamInputs({ ...SWEEP_DEFAULTS[nextType] });
    setSawProgress(false);
    reset();
  }, [reset]);

  const handleParamInputChange = useCallback((key: string, value: string) => {
    setParamInputs((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSubmit = useCallback(async (payload: SweepStartPayload) => {
    if (payload.valid_combos > MAX_SWEEP_COMBOS) {
      toast.error(`合法組合數 ${payload.valid_combos} 超過上限 ${MAX_SWEEP_COMBOS}`);
      return;
    }
    setSawProgress(false);
    await start("backtest_sweep", {
      market: payload.market,
      symbol: payload.symbol,
      start_date: payload.start_date,
      end_date: payload.end_date,
      strategy_type: payload.strategy_type,
      param_candidates: payload.param_candidates,
      initial_capital: payload.initial_capital,
    });
  }, [start, toast]);

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

  const handleCopyParams = useCallback(async (params: Record<string, number>) => {
    const text = paramsToText(params);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        toast.success(`參數已複製：${text}`);
        return;
      }
      toast.info("此瀏覽器不支援剪貼簿 API");
    } catch {
      toast.error("複製失敗，請手動複製參數。");
    }
  }, [toast]);

  return (
    <div className="space-y-4">
      <ParamGridForm
        market={market}
        symbol={symbol}
        startDate={startDate}
        endDate={endDate}
        strategyType={strategyType}
        paramInputs={paramInputs}
        initialCapital={initialCapital}
        disabled={isRunning}
        onMarketChange={handleMarketChange}
        onSymbolChange={setSymbol}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onStrategyTypeChange={handleStrategyTypeChange}
        onParamInputChange={handleParamInputChange}
        onInitialCapitalChange={setInitialCapital}
        onSubmit={handleSubmit}
      />

      {status === "idle" && (
        <p className="text-sm text-slate-400">設定參數範圍後按「開始掃描」</p>
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
              <div className="grid grid-cols-3 gap-2">
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </div>
              <TableSkeleton rows={8} columns={9} />
              <ChartSkeleton height={260} />
            </>
          ) : (
            <p className="text-sm text-slate-400">掃描執行中，等待結果彙整…</p>
          )}
        </>
      )}

      {(status === "complete" || status === "cancelled") && result && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              總組合：{result.total_combos}
            </div>
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              合法組合：{result.valid_combos}
            </div>
            <div className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
              已完成：{result.results.length}/{result.valid_combos}
            </div>
          </div>

          <div className="flex items-center justify-end">
            <button
              type="button"
              data-testid="download-sweep-csv-btn"
              disabled={!result}
              onClick={handleDownloadCsv}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
            >
              匯出 CSV
            </button>
          </div>

          <SweepRankingTable rows={result.results} topN={20} />

          {heatmapEnabled ? (
            <SweepHeatmap rows={result.results} onCopyParams={handleCopyParams} />
          ) : (
            <div className="rounded border border-slate-700 p-3 text-xs text-slate-400">
              參數維度超過 2 個時不顯示 Heatmap，請改看排名表。
            </div>
          )}

          {status === "cancelled" && (
            <p className="text-xs text-slate-500">（掃描已取消，顯示取消前已完成的結果）</p>
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
