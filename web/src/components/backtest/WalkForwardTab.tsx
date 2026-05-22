"use client";

// WFA tab — Walk-Forward Analysis (Phase 10-E-4)

import { useCallback, useMemo, useState } from "react";
import { MarketSwitcher } from "@/components/market-switcher";
import { StockSelector } from "@/components/stock-selector";
import { CardSkeleton, TableSkeleton } from "@/components/skeletons";
import { useBacktestJob } from "@/hooks/use-backtest-job";
import { useToast } from "@/hooks/use-toast";
import type { Market } from "@/types/market";
import { BacktestProgressBar } from "./BacktestProgressBar";
import { DateRangePicker } from "./DateRangePicker";
import { WfaSummaryCards } from "./WfaSummaryCards";
import { WfaWindowTable } from "./WfaWindowTable";
import { WfaStabilityTable } from "./WfaStabilityTable";
import {
  SWEEP_STRATEGY_LABELS,
  SWEEP_PARAM_LABELS,
  analyzeSweepInputs,
  createDefaultParamInputs,
} from "./sweep-helpers";
import { SWEEP_DEFAULTS, SWEEP_PARAM_SPECS } from "./sweep-constants";
import type { SweepStrategyType } from "./sweep-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const OPTIMIZE_METRIC_OPTIONS = [
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "total_return", label: "總報酬" },
  { value: "annual_return", label: "年化報酬" },
] as const;

const MAX_WFA_WINDOWS = 10;
const MIN_WFA_WINDOWS = 3;

function estimateWindowCount(
  startDate: string,
  endDate: string,
  isMonths: number,
  oosMonths: number,
  stepMonths: number,
): { estimated: number; required: number; actual: number } {
  try {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const actual =
      (end.getFullYear() - start.getFullYear()) * 12 +
      (end.getMonth() - start.getMonth());
    const required =
      isMonths + oosMonths + (MIN_WFA_WINDOWS - 1) * stepMonths;
    const raw =
      stepMonths > 0
        ? Math.floor((actual - isMonths - oosMonths) / stepMonths) + 1
        : 0;
    const estimated = Math.min(Math.max(0, raw), MAX_WFA_WINDOWS);
    return { estimated, required, actual };
  } catch {
    return { estimated: 0, required: 0, actual: 0 };
  }
}

interface WfaResult {
  symbol: string;
  market: Market;
  currency: string;
  strategy_type: string;
  optimize_metric: string;
  total_window_count: number;
  valid_window_count: number;
  skipped_window_count: number;
  windows: import("./WfaWindowTable").WfaWindowRow[];
  aggregate: {
    oos_total_return: number | null;
    oos_annual_return: number | null;
    oos_max_drawdown: number | null;
    oos_sharpe_ratio: number | null;
    oos_win_rate: number | null;
    avg_degradation: number | null;
  };
  parameter_stability: {
    overall_status: string;
    params: Record<
      string,
      { values: number[]; cv: number | null; mean: number; std: number; status: string }
    >;
  };
}

function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match?.[1] ?? fallback;
}

export function WalkForwardTab() {
  const toast = useToast();
  const [market, setMarket] = useState<Market>("tw");
  const [symbol, setSymbol] = useState("");
  const [startDate, setStartDate] = useState("2018-01-01");
  const [endDate, setEndDate] = useState("2026-04-30");
  const [strategyType, setStrategyType] = useState<SweepStrategyType>("moving_average_cross");
  const [paramInputs, setParamInputs] = useState<Record<string, string>>(
    createDefaultParamInputs("moving_average_cross"),
  );
  const [isMonths, setIsMonths] = useState(12);
  const [oosMonths, setOosMonths] = useState(3);
  const [stepMonths, setStepMonths] = useState(3);
  const [optimizeMetric, setOptimizeMetric] = useState("sharpe_ratio");
  const [initialCapital, setInitialCapital] = useState(1_000_000);
  const [firstWindowDone, setFirstWindowDone] = useState(false);

  const { jobId, status, wfaProgress, result, error, start, cancel, reset } =
    useBacktestJob<WfaResult>({
      disableDefaultToasts: true,
      onComplete: (payload) => {
        const n = payload?.valid_window_count ?? payload?.total_window_count ?? 0;
        toast.success(`WFA 分析完成（${n} 段視窗）`);
      },
      onCancelled: (payload) => {
        const done = payload?.windows?.length ?? 0;
        const total = payload?.total_window_count ?? 0;
        toast.info(`WFA 已取消（已完成 ${done}/${total} 段視窗）`);
      },
      onError: (err) => {
        toast.error(`WFA 失敗：${err.message}`);
      },
      onWfaProgress: (wp) => {
        if (wp.phase === "done") setFirstWindowDone(true);
      },
    });

  const isRunning = status === "running";

  const analysis = useMemo(
    () => analyzeSweepInputs(strategyType, paramInputs),
    [strategyType, paramInputs],
  );

  const windowEstimate = useMemo(
    () => estimateWindowCount(startDate, endDate, isMonths, oosMonths, stepMonths),
    [startDate, endDate, isMonths, oosMonths, stepMonths],
  );

  const isInsufficient = windowEstimate.actual < windowEstimate.required;
  const canSubmit =
    !isRunning &&
    symbol.trim().length > 0 &&
    !analysis.hasParseError &&
    analysis.validCombos > 0 &&
    !isInsufficient;

  const handleMarketChange = useCallback(
    (next: Market) => {
      setMarket(next);
      setSymbol("");
      setFirstWindowDone(false);
      reset();
    },
    [reset],
  );

  const handleStrategyTypeChange = useCallback(
    (next: SweepStrategyType) => {
      setStrategyType(next);
      setParamInputs({ ...SWEEP_DEFAULTS[next] });
      setFirstWindowDone(false);
      reset();
    },
    [reset],
  );

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setFirstWindowDone(false);
    await start("backtest_wfa", {
      market,
      symbol: symbol.trim(),
      start_date: startDate,
      end_date: endDate,
      strategy_type: strategyType,
      param_candidates: analysis.paramCandidates,
      is_months: isMonths,
      oos_months: oosMonths,
      step_months: stepMonths,
      optimize_metric: optimizeMetric,
      initial_capital: initialCapital,
    });
  }, [
    canSubmit,
    start,
    market,
    symbol,
    startDate,
    endDate,
    strategyType,
    analysis.paramCandidates,
    isMonths,
    oosMonths,
    stepMonths,
    optimizeMetric,
    initialCapital,
  ]);

  const handleDownloadCsv = useCallback(
    async (part: "window" | "stability") => {
      if (!jobId || !result) return;
      try {
        const resp = await fetch(
          `${API_BASE}/api/jobs/${jobId}/result?format=csv&part=${part}`,
        );
        if (!resp.ok) {
          toast.error(`下載失敗：HTTP ${resp.status}`);
          return;
        }
        const blob = await resp.blob();
        const fallback =
          part === "stability"
            ? `wfa_stability_${result.symbol}.csv`
            : `wfa_window_${result.symbol}.csv`;
        const filename = parseFilename(resp.headers.get("content-disposition"), fallback);
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
    },
    [jobId, result, toast],
  );

  const paramKeys = SWEEP_PARAM_SPECS[strategyType] ?? [];

  return (
    <div className="space-y-4">
      {/* ── Form ─────────────────────────────────────────── */}
      <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-200">Walk-Forward 設定</h3>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Market */}
          <div>
            <label className="mb-1 block text-xs text-slate-400">市場</label>
            <MarketSwitcher value={market} onChange={handleMarketChange} />
          </div>

          {/* Symbol */}
          <div>
            <label className="mb-1 block text-xs text-slate-400">股票代碼</label>
            <StockSelector
              market={market}
              value={symbol}
              onChange={setSymbol}
            />
          </div>

          {/* Date range */}
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs text-slate-400">回測區間</label>
            <DateRangePicker
              startDate={startDate}
              endDate={endDate}
              onStartChange={setStartDate}
              onEndChange={setEndDate}
            />
          </div>

          {/* Strategy type */}
          <div>
            <label className="mb-1 block text-xs text-slate-400">策略</label>
            <select
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={strategyType}
              disabled={isRunning}
              onChange={(e) => handleStrategyTypeChange(e.target.value as SweepStrategyType)}
            >
              {Object.entries(SWEEP_STRATEGY_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Optimize metric */}
          <div>
            <label className="mb-1 block text-xs text-slate-400">最佳化指標</label>
            <select
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={optimizeMetric}
              disabled={isRunning}
              onChange={(e) => setOptimizeMetric(e.target.value)}
            >
              {OPTIMIZE_METRIC_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {/* Initial capital */}
          <div>
            <label className="mb-1 block text-xs text-slate-400">初始資金</label>
            <input
              type="number"
              min={10000}
              step={10000}
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={initialCapital}
              disabled={isRunning}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
            />
          </div>
        </div>

        {/* IS/OOS/Step months */}
        <div className="mt-3 grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">IS 月數（樣本內）</label>
            <input
              type="number"
              min={1}
              max={60}
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={isMonths}
              disabled={isRunning}
              onChange={(e) => setIsMonths(Math.max(1, parseInt(e.target.value, 10) || 1))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">OOS 月數（樣本外）</label>
            <input
              type="number"
              min={1}
              max={24}
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={oosMonths}
              disabled={isRunning}
              onChange={(e) => setOosMonths(Math.max(1, parseInt(e.target.value, 10) || 1))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">步進月數</label>
            <input
              type="number"
              min={1}
              max={24}
              className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
              value={stepMonths}
              disabled={isRunning}
              onChange={(e) => setStepMonths(Math.max(1, parseInt(e.target.value, 10) || 1))}
            />
          </div>
        </div>

        {/* Param grid inputs */}
        {paramKeys.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-slate-400">IS 掃描參數（逗號分隔，同參數掃描）</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {paramKeys.map((key) => (
                <div key={key}>
                  <label className="mb-0.5 block text-xs text-slate-400">
                    {SWEEP_PARAM_LABELS[key] ?? key}
                  </label>
                  <input
                    type="text"
                    className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-slate-200 disabled:opacity-50"
                    value={paramInputs[key] ?? ""}
                    disabled={isRunning}
                    onChange={(e) =>
                      setParamInputs((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Estimates & warnings */}
        <div className="mt-3 space-y-1">
          {isInsufficient && (
            <p className="text-xs text-red-400">
              ⚠ 日期區間不足：需要 {windowEstimate.required} 個月，目前 {windowEstimate.actual}{" "}
              個月
            </p>
          )}
          {!isInsufficient && windowEstimate.estimated > 0 && (
            <p className="text-xs text-slate-400">
              預估 {windowEstimate.estimated} 段視窗 × {analysis.validCombos} 組合 = 最多{" "}
              {windowEstimate.estimated * analysis.validCombos} 次回測
            </p>
          )}
          {analysis.hasParseError && (
            <p className="text-xs text-red-400">⚠ 參數格式錯誤，請確認逗號分隔值正確</p>
          )}
        </div>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            data-testid="wfa-submit-btn"
            disabled={!canSubmit}
            onClick={handleSubmit}
            className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
          >
            開始 Walk-Forward
          </button>
          {isRunning && (
            <button
              type="button"
              onClick={cancel}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700"
            >
              取消
            </button>
          )}
        </div>
      </div>

      {/* ── Progress ─────────────────────────────────────── */}
      {isRunning && (
        <div className="space-y-2" data-testid="wfa-progress-section">
          <BacktestProgressBar
            current={wfaProgress?.windowId}
            total={wfaProgress?.totalWindows}
            phase={wfaProgress?.phase ?? "running"}
            onCancel={cancel}
          />
          {wfaProgress && (
            <p className="text-xs text-slate-400">
              視窗 {wfaProgress.windowId}/{wfaProgress.totalWindows} —{" "}
              {wfaProgress.phase === "is_sweep"
                ? `IS 掃描${wfaProgress.sweepCurrent !== undefined ? ` (${wfaProgress.sweepCurrent}/${wfaProgress.sweepTotal})` : ""}`
                : wfaProgress.phase === "oos_validate"
                  ? "OOS 驗證中…"
                  : "視窗完成"}
            </p>
          )}
          {!firstWindowDone && (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {[1, 2, 3, 4, 5].map((i) => (
                  <CardSkeleton key={i} />
                ))}
              </div>
              <TableSkeleton rows={4} columns={8} />
              <TableSkeleton rows={3} columns={5} />
            </>
          )}
        </div>
      )}

      {/* ── Results ──────────────────────────────────────── */}
      {(status === "complete" || status === "cancelled") && result && (
        <div className="space-y-4" data-testid="wfa-results">
          {status === "cancelled" && (
            <p className="text-xs text-slate-500">
              （WFA 已取消，顯示取消前已完成的視窗）
            </p>
          )}

          {/* Summary cards */}
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              彙整 Summary
            </h4>
            <WfaSummaryCards
              aggregate={result.aggregate}
              validWindowCount={result.valid_window_count}
              totalWindowCount={result.total_window_count}
              currency={result.currency}
            />
          </section>

          {/* CSV download buttons */}
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="download-wfa-window-csv"
              onClick={() => handleDownloadCsv("window")}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
            >
              匯出視窗表 CSV
            </button>
            <button
              type="button"
              data-testid="download-wfa-stability-csv"
              onClick={() => handleDownloadCsv("stability")}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
            >
              匯出穩定性表 CSV
            </button>
          </div>

          {/* Window table */}
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              視窗明細 Windows
            </h4>
            <WfaWindowTable windows={result.windows} />
          </section>

          {/* Stability table */}
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              參數穩定性 Stability
            </h4>
            <WfaStabilityTable params={result.parameter_stability.params} />
          </section>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────── */}
      {status === "error" && error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-rose-300">
          <p className="font-semibold">執行失敗</p>
          <p className="mt-1 text-sm">
            {error.message}（代碼：{error.code}）
          </p>
        </div>
      )}

      {status === "idle" && (
        <p className="text-sm text-slate-400">設定參數後按「開始 Walk-Forward」</p>
      )}
    </div>
  );
}
