"use client";

// Single backtest run tab (Phase 10-E-1)

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useCommandPaletteEntry } from "@/hooks/use-command-palette";
import { useBacktestJob } from "@/hooks/use-backtest-job";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/skeletons";
import { MarketSwitcher } from "@/components/market-switcher";
import { StockSelector } from "@/components/stock-selector";
import { BacktestProgressBar } from "./BacktestProgressBar";
import { TearsheetCards } from "./TearsheetCards";
import { CandleChartWithMarkers } from "./CandleChartWithMarkers";
import { EquityCurveChart } from "./EquityCurveChart";
import { TradesTable } from "./TradesTable";
import { StrategyPresetSelect } from "./StrategyPresetSelect";
import { DateRangePicker } from "./DateRangePicker";
import { EngineSelect } from "./EngineSelect";
import type { Market } from "@/types/market";
import type { EngineType } from "@/types/backtest";

// ── Result schema (matches backend 10-E-1 result) ────────────────────────────

interface BacktestMetrics {
  total_trades: number | null;
  total_return: number | null;
  annual_return: number | null;
  max_drawdown: number | null;
  sharpe_ratio: number | null;
}

interface Trade {
  entry_date: string;
  exit_date: string;
  side: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  pnl: number;
  return_pct: number;
}

interface Signal {
  date: string;
  side: "buy" | "sell";
  price: number;
}

interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface BacktestRunResult {
  symbol: string;
  market: Market;
  currency: string;
  engine: string;
  strategy_type: string;
  strategy_params: Record<string, number>;
  metrics: BacktestMetrics | null;
  equity_curve: Array<{ date: string; value: number }>;
  trades: Trade[];
  signals: Signal[];
  price_data: PriceBar[];
  dca_warning: string | null;
}

// ── MA overlay inference ──────────────────────────────────────────────────────

function inferMaOverlay(
  strategyType: string,
  params: Record<string, number>,
): Array<{ name: string; period: number; color: string }> {
  if (strategyType === "moving_average_cross") {
    return [
      { name: `MA${params.short_window ?? 20}`, period: params.short_window ?? 20, color: "#60a5fa" },
      { name: `MA${params.long_window ?? 60}`, period: params.long_window ?? 60, color: "#f59e0b" },
    ];
  }
  if (strategyType === "bollinger_band") {
    return [{ name: `MA${params.period ?? 20}`, period: params.period ?? 20, color: "#60a5fa" }];
  }
  if (strategyType === "bias") {
    return [{ name: `MA${params.ma_period ?? 20}`, period: params.ma_period ?? 20, color: "#60a5fa" }];
  }
  return [];
}

// ── Main component ────────────────────────────────────────────────────────────

export function SingleRunTab() {
  const router = useRouter();
  const { status, progress, result, error, start, cancel, reset } =
    useBacktestJob<BacktestRunResult>();

  const [market, setMarket] = useState<Market>("tw");
  const [symbol, setSymbol] = useState("");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [engine, setEngine] = useState<EngineType>("vectorized");
  const [presetIndex, setPresetIndex] = useState(0);
  const [initialCapital, setInitialCapital] = useState(1_000_000);

  // Command Palette entries
  useCommandPaletteEntry({ id: "bt-single", label: "回測：單次", action: () => router.push("/backtest?tab=single") });
  useCommandPaletteEntry({ id: "bt-batch", label: "回測：策略比較", action: () => router.push("/backtest?tab=batch") });
  useCommandPaletteEntry({ id: "bt-sweep", label: "回測：參數掃描", action: () => router.push("/backtest?tab=sweep") });
  useCommandPaletteEntry({ id: "bt-wfa", label: "回測：Walk-Forward", action: () => router.push("/backtest?tab=wfa") });

  const handleMarketChange = useCallback(
    (m: Market) => {
      if (m !== market) {
        setMarket(m);
        setSymbol("");
        reset();
      }
    },
    [market, reset],
  );

  const handleSubmit = useCallback(async () => {
    if (!symbol) return;
    await start("backtest_run", {
      market,
      symbol,
      start_date: startDate,
      end_date: endDate,
      strategy_preset_index: presetIndex,
      engine,
      initial_capital: initialCapital,
    });
  }, [start, market, symbol, startDate, endDate, presetIndex, engine, initialCapital]);

  const isRunning = status === "running";

  const maOverlay =
    result?.strategy_type
      ? inferMaOverlay(result.strategy_type, result.strategy_params ?? {})
      : [];

  return (
    <div className="space-y-4">
      {/* ── Form ── */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">市場</label>
          <MarketSwitcher value={market} onChange={handleMarketChange} />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">股票代碼</label>
          <StockSelector
            market={market}
            value={symbol}
            onChange={setSymbol}
          />
        </div>

        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onStartChange={setStartDate}
          onEndChange={setEndDate}
          disabled={isRunning}
        />

        <EngineSelect
          value={engine}
          onChange={setEngine}
          disabled={isRunning}
        />

        <StrategyPresetSelect
          value={presetIndex}
          onChange={setPresetIndex}
          disabled={isRunning}
        />

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">初始資金</label>
          <input
            type="number"
            data-testid="initial-capital-input"
            value={initialCapital}
            onChange={(e) => setInitialCapital(Number(e.target.value))}
            disabled={isRunning}
            className="w-32 rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
            min={1}
            step={10000}
          />
        </div>

        <button
          type="button"
          data-testid="start-backtest-btn"
          onClick={handleSubmit}
          disabled={isRunning || !symbol}
          className="rounded bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          開始回測
        </button>
      </div>

      {/* ── Idle ── */}
      {status === "idle" && (
        <p className="text-sm text-slate-400">設定參數後按「開始回測」</p>
      )}

      {/* ── Running ── */}
      {status === "running" && (
        <>
          <BacktestProgressBar
            phase={progress?.phase}
            onCancel={cancel}
          />
          <div className="grid grid-cols-5 gap-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
          <ChartSkeleton height={400} />
          <ChartSkeleton height={200} />
          <TableSkeleton rows={5} columns={7} />
        </>
      )}

      {/* ── Complete ── */}
      {(status === "complete" || status === "cancelled") && result && (
        <>
          {result.dca_warning && (
            <div className="rounded border border-amber-600/40 bg-amber-600/10 px-3 py-2 text-xs text-amber-300">
              {result.dca_warning}
            </div>
          )}

          {result.metrics && (
            <TearsheetCards
              metrics={result.metrics}
              currency={result.currency}
              isDca={result.strategy_type === "dollar_cost_averaging"}
            />
          )}

          {result.price_data.length > 0 && (
            <CandleChartWithMarkers
              priceData={result.price_data}
              signals={result.signals}
              market={result.market}
              maOverlay={maOverlay}
              height={400}
            />
          )}

          {result.equity_curve.length > 0 && (
            <EquityCurveChart
              series={[{ name: "資金曲線", data: result.equity_curve, color: "#60a5fa" }]}
              height={200}
            />
          )}

          {result.trades.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-slate-300">交易明細</h3>
              <TradesTable trades={result.trades} currency={result.currency} />
            </div>
          )}

          {status === "cancelled" && (
            <p className="text-xs text-slate-500">（回測已取消，顯示取消前已完成的結果）</p>
          )}
        </>
      )}

      {/* ── Error ── */}
      {status === "error" && error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-rose-300">
          <p className="font-semibold">執行失敗</p>
          <p className="mt-1 text-sm">
            {error.message}（代碼：{error.code}）
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-3 rounded bg-rose-500 px-3 py-1 text-sm text-white hover:bg-rose-400"
          >
            重試
          </button>
        </div>
      )}
    </div>
  );
}
