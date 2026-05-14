"use client";

import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { RefreshCw, Search, X } from "lucide-react";
import { MarketSwitcher } from "@/components/market-switcher";
import { StockSelector } from "@/components/stock-selector";
import { CandlestickChart } from "@/components/dashboard/candlestick-chart";
import { HelpTooltip } from "@/components/dashboard/help-tooltip";
import { DASHBOARD_TOOLTIP_TEXT } from "@/components/dashboard/tooltip-text";
import { useDashboard } from "@/lib/hooks/useDashboard";
import { changeColor, formatNumber, formatPct } from "@/lib/formatters";
import type {
  BidAskStructure,
  CandlePattern,
  ChartPatternResult,
  ChipRecentRow,
  ChipSummary,
  DashboardAnalysis,
  DashboardPayloadResponse,
  MultiTimeframeAnalysis,
  RealtimeQuote,
  TechnicalSummary,
  USIntradaySnapshot,
} from "@/types/analysis";
import type { Market } from "@/types/market";

type ChartInterval = "day" | "week" | "month" | "minute";

function formatSignedValue(value: number, decimals = 0): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, decimals)}`;
}

function scoreClass(score: number): string {
  if (score >= 0.7) return "text-rise";
  if (score >= 0.3) return "text-amber-300";
  return "text-fall";
}

function normalizeSymbol(raw: string): string {
  return raw.trim().toUpperCase();
}

function renderRatio(ratio: number): string {
  return `${(ratio * 100).toFixed(2)}%`;
}

function mapPatternRows(
  candles: CandlePattern[],
  charts: ChartPatternResult[],
): Array<{ name: string; formed: boolean; description: string }> {
  const c = candles.map((item) => ({
    name: item.name,
    formed: item.detected,
    description: item.description,
  }));
  const p = charts.map((item) => ({
    name: item.pattern_type,
    formed: item.formed,
    description: item.description,
  }));
  return [...c, ...p];
}

function HeaderRow({
  quote,
  intradaySnapshot,
  market,
}: {
  quote: RealtimeQuote | null;
  intradaySnapshot: USIntradaySnapshot | null;
  market: Market;
}) {
  if (!quote && !intradaySnapshot) return null;
  if (!quote && intradaySnapshot) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
        <div className="grid grid-cols-2 gap-3 text-xs text-slate-300 md:grid-cols-6">
          <div>
            <div className="text-slate-500">Price</div>
            <div className="text-slate-100 [font-family:var(--font-mono)]">
              {formatNumber(intradaySnapshot.price, 2)}
            </div>
          </div>
          <div>
            <div className="text-slate-500">PC</div>
            <div className="text-slate-100 [font-family:var(--font-mono)]">
              {formatNumber(intradaySnapshot.previous_raw_close, 2)}
            </div>
          </div>
          <div>
            <div className="text-slate-500">Change</div>
            <div className={`${changeColor(intradaySnapshot.change, market)} [font-family:var(--font-mono)]`}>
              {formatSignedValue(intradaySnapshot.change, 2)} ({formatPct(intradaySnapshot.change_pct, 2)})
            </div>
          </div>
          <div>
            <div className="text-slate-500">V</div>
            <div className="text-slate-100 [font-family:var(--font-mono)]">
              {formatNumber(intradaySnapshot.volume, 0)}
            </div>
          </div>
          <div>
            <div className="text-slate-500">Source</div>
            <div className="text-slate-100 [font-family:var(--font-mono)]">
              {intradaySnapshot.source}
            </div>
          </div>
          <div>
            <div className="text-slate-500">Time</div>
            <div className="text-slate-100 [font-family:var(--font-mono)]">
              {intradaySnapshot.timestamp.slice(0, 19)}
            </div>
          </div>
        </div>
      </section>
    );
  }
  if (!quote) return null;
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
      <div className="grid grid-cols-2 gap-3 text-xs text-slate-300 md:grid-cols-7">
        <div>
          <div className="text-slate-500">O</div>
          <div className="[font-family:var(--font-mono)]">
            {formatNumber(quote.open, 2)}
          </div>
        </div>
        <div>
          <div className="text-slate-500">H</div>
          <div className="[font-family:var(--font-mono)]">
            {formatNumber(quote.high, 2)}
          </div>
        </div>
        <div>
          <div className="text-slate-500">L</div>
          <div className="[font-family:var(--font-mono)]">
            {formatNumber(quote.low, 2)}
          </div>
        </div>
        <div>
          <div className="text-slate-500">PC</div>
          <div className="[font-family:var(--font-mono)]">
            {formatNumber(quote.yesterday_close, 2)}
          </div>
        </div>
        <div>
          <div className="text-slate-500">V</div>
          <div className="[font-family:var(--font-mono)]">
            {formatNumber(quote.volume, market === "tw" ? 0 : 0)}
          </div>
        </div>
        <div>
          <div className="text-slate-500">買量</div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(1, "tw")}`}>
            {formatNumber(
              (quote.best_bid_vol?.[0] ?? 0) + (quote.best_bid_vol?.[1] ?? 0),
              0,
            )}
          </div>
        </div>
        <div>
          <div className="text-slate-500">賣量</div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(-1, "tw")}`}>
            {formatNumber(
              (quote.best_ask_vol?.[0] ?? 0) + (quote.best_ask_vol?.[1] ?? 0),
              0,
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function TechnicalPanel({ technical }: { technical: TechnicalSummary }) {
  const rows: Array<{ key: keyof typeof DASHBOARD_TOOLTIP_TEXT; label: string; value: string }> = [
    { key: "trend_direction", label: "趨勢方向", value: technical.trend_direction },
    { key: "ma_status", label: "MA 狀態", value: technical.ma_status },
    { key: "kd_status", label: "KD", value: technical.kd_status },
    { key: "macd_status", label: "MACD", value: technical.macd_status },
    { key: "volume_status", label: "成交量", value: technical.volume_status },
    {
      key: "volume_price_relation",
      label: "量價關係",
      value: technical.volume_price_relation,
    },
    { key: "ma_bias", label: "乖離 MA20", value: technical.ma_bias },
  ];
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">技術分析總覽</h3>
        <span className="text-xs text-slate-500">近 60 日</span>
      </div>
      <div className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-[90px_1fr] items-start gap-2 border-b border-slate-800/70 pb-1.5 text-sm"
          >
            <div className="flex items-center gap-1 text-slate-300">
              {row.label}
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT[row.key]} />
            </div>
            <div className="[font-family:var(--font-mono)] text-slate-100">{row.value}</div>
          </div>
        ))}
        <div className="grid grid-cols-[90px_1fr] items-start gap-2 pt-1.5 text-sm">
          <div className="flex items-center gap-1 text-slate-300">
            短線分數
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.short_term_score} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${scoreClass(technical.short_term_score)}`}>
            {(technical.short_term_score * 100).toFixed(0)}% {technical.short_term_label}
          </div>
        </div>
      </div>
    </section>
  );
}

function LevelsPanel({ technical }: { technical: TechnicalSummary }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">關鍵價位</h3>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-400">
            壓力區
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.resistance} />
          </div>
          <div className="text-2xl font-semibold text-rise [font-family:var(--font-mono)]">
            {technical.resistance_levels
              .map((item) => formatNumber(item.value, 0))
              .join(" / ")}
          </div>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-400">
            支撐區
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.support} />
          </div>
          <div className="text-2xl font-semibold text-fall [font-family:var(--font-mono)]">
            {technical.support_levels
              .map((item) => formatNumber(item.value, 0))
              .join(" / ")}
          </div>
        </div>
      </div>
    </section>
  );
}

function ChipRecentDialog({ rows }: { rows: ChipRecentRow[] }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
        >
          查看 5 日明細
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70" />
        <Dialog.Content className="fixed right-0 top-0 z-50 h-full w-full max-w-xl border-l border-slate-800 bg-slate-950 p-4 text-slate-100">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-sm font-semibold">
              三大法人 近 5 交易日（張）
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-md border border-slate-700 p-1 hover:bg-slate-800"
                aria-label="關閉"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/80 text-slate-300">
                <tr>
                  <th className="px-3 py-2 text-left">日期</th>
                  <th className="px-3 py-2 text-right">外資</th>
                  <th className="px-3 py-2 text-right">投信</th>
                  <th className="px-3 py-2 text-right">自營商</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.日期} className="border-t border-slate-800 text-slate-100">
                    <td className="px-3 py-2 [font-family:var(--font-mono)]">{row.日期}</td>
                    <td
                      className={`px-3 py-2 text-right [font-family:var(--font-mono)] ${changeColor(row.外資, "tw")}`}
                    >
                      {formatSignedValue(row.外資, 0)}
                    </td>
                    <td
                      className={`px-3 py-2 text-right [font-family:var(--font-mono)] ${changeColor(row.投信, "tw")}`}
                    >
                      {formatSignedValue(row.投信, 0)}
                    </td>
                    <td
                      className={`px-3 py-2 text-right [font-family:var(--font-mono)] ${changeColor(row.自營商, "tw")}`}
                    >
                      {formatSignedValue(row.自營商, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ChipPanel({
  chip,
  bidAsk,
  chipRecent,
}: {
  chip: ChipSummary | null;
  bidAsk: BidAskStructure | null;
  chipRecent: ChipRecentRow[];
}) {
  if (!chip) return null;
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">籌碼分析 近 5 日</h3>
        {chipRecent.length > 0 ? <ChipRecentDialog rows={chipRecent} /> : null}
      </div>

      {bidAsk ? (
        <div className="mb-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-300">
            買賣力道
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.bid_ask} />
          </div>
          <div className="text-sm [font-family:var(--font-mono)] text-slate-100">
            {bidAsk.label}
          </div>
          <div className="text-xs text-slate-400 [font-family:var(--font-mono)]">
            買方 {renderRatio(bidAsk.bid_ratio)} / 賣方 {renderRatio(bidAsk.ask_ratio)}
          </div>
        </div>
      ) : null}

      <div className="space-y-1.5 text-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
          <div className="flex items-center gap-1 text-slate-300">
            外資
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.foreign} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(chip.foreign_net_n_days, "tw")}`}>
            {chip.foreign_label}
          </div>
        </div>
        <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
          <div className="flex items-center gap-1 text-slate-300">
            投信
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.trust} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(chip.trust_net_n_days, "tw")}`}>
            {chip.trust_label}
          </div>
        </div>
        <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
          <div className="flex items-center gap-1 text-slate-300">
            自營商
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.dealer} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(chip.dealer_net_n_days, "tw")}`}>
            {chip.dealer_label}
          </div>
        </div>
      </div>

      <div className="my-3 grid grid-cols-2 gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-sm">
        <div>
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-400">
            融資
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.margin_balance} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(chip.margin_balance_change, "tw")}`}>
            {formatSignedValue(chip.margin_balance_change, 0)} 張
          </div>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-400">
            融券
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.short_balance} />
          </div>
          <div className={`[font-family:var(--font-mono)] ${changeColor(chip.short_balance_change, "tw")}`}>
            {formatSignedValue(chip.short_balance_change, 0)} 張
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1 text-slate-300">
          籌碼集中度
          <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.chip_concentration} />
        </div>
        <div className="[font-family:var(--font-mono)] text-slate-100">{chip.chip_concentration}</div>
      </div>
    </section>
  );
}

function PatternsPanel({
  candles,
  charts,
}: {
  candles: CandlePattern[];
  charts: ChartPatternResult[];
}) {
  const rows = mapPatternRows(candles, charts);
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-100">K 線型態</h3>
      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/80 text-slate-300">
            <tr>
              <th className="px-3 py-2 text-left">型態</th>
              <th className="px-3 py-2 text-left">狀態</th>
              <th className="px-3 py-2 text-left">說明</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-t border-slate-800">
                <td className="px-3 py-2 [font-family:var(--font-mono)]">{row.name}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      row.formed
                        ? "bg-rise/15 text-rise"
                        : "bg-slate-700/60 text-slate-300"
                    }`}
                  >
                    {row.formed ? "成立" : "未成"}
                  </span>
                </td>
                <td className="px-3 py-2 text-slate-300">{row.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MultiTimeframePanel({
  mtf,
  technical,
}: {
  mtf: MultiTimeframeAnalysis;
  technical: TechnicalSummary;
}) {
  const rows = [
    { label: "日 K", key: "timeframe_daily", value: mtf.daily },
    { label: "週 K", key: "timeframe_weekly", value: mtf.weekly },
    { label: "月 K", key: "timeframe_monthly", value: mtf.monthly },
  ] as const;
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-100">多週期 · 量價</h3>
      <div className="space-y-2 border-b border-slate-800 pb-3">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[50px_70px_1fr] items-center gap-2 text-sm">
            <div className="flex items-center gap-1 text-slate-300">
              {row.label}
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT[row.key]} />
            </div>
            <span className="rounded-full bg-rise/15 px-2 py-0.5 text-center text-rise">
              {row.value.trend_direction}
            </span>
            <span className="text-slate-100 [font-family:var(--font-mono)]">{row.value.strength}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 space-y-3">
        <div>
          <div className="mb-1 flex items-center gap-1 text-sm text-slate-300">
            量價背離
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.volume_price_divergence} />
          </div>
          <p className="text-sm text-slate-100">{technical.volume_price_divergence}</p>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1 text-sm text-slate-300">
            均線乖離
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.ma_bias} />
          </div>
          <p className="text-sm text-slate-100">{technical.ma_bias}</p>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1 text-sm text-slate-300">
            操作觀察
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.operation_observation} />
          </div>
          <p className="text-sm text-slate-100">{technical.operation_observation}</p>
        </div>
      </div>
    </section>
  );
}

function AiPanel({
  aiEnabled,
  analysis,
  onEnableHint,
}: {
  aiEnabled: boolean;
  analysis: DashboardAnalysis | null;
  onEnableHint: () => void;
}) {
  if (!aiEnabled) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">隔日操作劇本</h3>
          <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
            AI · OFF
          </span>
        </div>
        <div className="rounded-lg border border-dashed border-slate-700 bg-slate-900/40 p-5 text-center">
          <p className="mb-4 text-sm text-slate-400">
            AI 已停用。啟用後將顯示三情境：開高走高 / 震盪整理 / 開低回測。
          </p>
          <button
            type="button"
            className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
            onClick={onEnableHint}
          >
            啟用 AI 預覽
          </button>
        </div>
      </section>
    );
  }

  if (!analysis) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">隔日操作劇本</h3>
        <p className="text-sm text-slate-300">AI 分析失敗，請稍後重試。</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">隔日操作劇本</h3>
      <div className="space-y-2">
        {analysis.scenarios.map((scenario) => (
          <div key={scenario.name} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
            <div className="mb-1 text-sm font-medium text-slate-100">{scenario.name}</div>
            <div className="grid grid-cols-3 gap-2 text-xs text-slate-300">
              <div>
                <div className="text-slate-500">進場價</div>
                <div className="[font-family:var(--font-mono)]">{scenario.entry_range}</div>
              </div>
              <div>
                <div className="text-slate-500">停損</div>
                <div className="[font-family:var(--font-mono)]">{scenario.stop_loss}</div>
              </div>
              <div>
                <div className="text-slate-500">目標</div>
                <div className="[font-family:var(--font-mono)]">{scenario.target}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400">{analysis.conclusion}</p>
    </section>
  );
}

function DashboardMain({
  payload,
  market,
  interval,
  onIntervalChange,
}: {
  payload: DashboardPayloadResponse;
  market: Market;
  interval: ChartInterval;
  onIntervalChange: (next: ChartInterval) => void;
}) {
  const tabs: Array<{ value: ChartInterval; label: string }> = [
    { value: "day", label: "日 K" },
    { value: "week", label: "週 K" },
    { value: "month", label: "月 K" },
    { value: "minute", label: "分 K" },
  ];
  return (
    <>
      <HeaderRow
        quote={payload.quote}
        intradaySnapshot={payload.intraday_snapshot}
        market={market}
      />
      <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {tabs.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => onIntervalChange(tab.value)}
                  className={`rounded-md px-3 py-1.5 text-sm ${
                    interval === tab.value
                      ? "bg-slate-800 text-slate-100"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="text-xs text-slate-400">MA5 / MA20 / MA60</div>
          </div>
          <CandlestickChart
            market={market}
            interval={interval}
            daily={payload.daily_df}
            intraday={payload.intraday_df}
          />
        </div>
        <div className="space-y-3">
          <TechnicalPanel technical={payload.technical} />
          <LevelsPanel technical={payload.technical} />
          {market === "tw" ? (
            <ChipPanel
              chip={payload.chip}
              bidAsk={payload.bid_ask}
              chipRecent={payload.chip_recent_df}
            />
          ) : null}
        </div>
      </section>
    </>
  );
}

export default function DashboardPageClient() {
  const [market, setMarket] = useState<Market>("tw");
  const [pendingSymbol, setPendingSymbol] = useState("2330");
  const [symbol, setSymbol] = useState<string | null>("2330");
  const [interval, setInterval] = useState<ChartInterval>("day");
  const [aiHint, setAiHint] = useState<string>("");

  const { data, error, isLoading, mutate } = useDashboard(symbol, market);

  const titleSymbol = data?.symbol ?? symbol ?? "----";
  const titleName = data?.subject_name ?? "";
  const quote = data?.quote;
  const intradaySnapshot = data?.intraday_snapshot ?? null;

  const priceTone = useMemo(() => {
    if (quote) return changeColor(quote.change, market);
    if (intradaySnapshot) return changeColor(intradaySnapshot.change, market);
    return "text-slate-100";
  }, [quote, intradaySnapshot, market]);

  function handleAnalyze() {
    const normalized = normalizeSymbol(pendingSymbol);
    if (!normalized) return;
    setAiHint("");
    setSymbol(normalized);
  }

  return (
    <div className="-mx-4 -my-6 px-4 py-6 xl:px-6">
      <div className="mx-auto max-w-[2400px] space-y-3">
        <header className="space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-3xl font-semibold text-slate-100">個股分析</h1>
              <p className="text-sm text-slate-400">技術面 · 籌碼 · 型態 · AI 劇本</p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 xl:w-auto">
              <MarketSwitcher
                value={market}
                onChange={(next) => {
                  setMarket(next);
                  setPendingSymbol("");
                  setSymbol(null);
                  setAiHint("");
                }}
              />
              <StockSelector
                key={market}
                market={market}
                value={pendingSymbol}
                onInputChange={setPendingSymbol}
                onChange={(value) => {
                  setPendingSymbol(value);
                  setSymbol(normalizeSymbol(value));
                  setAiHint("");
                }}
                className="min-w-[220px] xl:min-w-[320px]"
              />
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                onClick={handleAnalyze}
              >
                <Search className="h-4 w-4" />
                分析
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-60"
                onClick={() => void mutate()}
                disabled={!symbol}
              >
                <RefreshCw className="h-4 w-4" />
                即時更新
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3">
            <div className="text-4xl font-semibold [font-family:var(--font-mono)] text-slate-100">
              {titleSymbol}
            </div>
            <div className="text-xl text-slate-200">{titleName}</div>
            {quote || intradaySnapshot ? (
              <>
                <div className={`text-5xl font-semibold [font-family:var(--font-mono)] ${priceTone}`}>
                  {formatNumber(quote?.price ?? intradaySnapshot?.price ?? 0, 2)}
                </div>
                <div className={`text-lg [font-family:var(--font-mono)] ${priceTone}`}>
                  {formatSignedValue(quote?.change ?? intradaySnapshot?.change ?? 0, 2)} (
                  {formatPct(quote?.change_pct ?? intradaySnapshot?.change_pct ?? 0, 2)})
                </div>
                <div className="text-sm text-slate-500">
                  {data?.analysis_time} · {interval === "minute" ? "分 K" : "日 K"}
                </div>
              </>
            ) : (
              <div className="text-sm text-slate-500">美股模式暫無即時報價</div>
            )}
          </div>
        </header>

        {!symbol ? (
          <section className="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-8 text-center text-slate-400">
            請輸入股票代碼或名稱後點選「分析」。
          </section>
        ) : null}

        {isLoading ? (
          <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="h-[620px] animate-pulse rounded-xl bg-slate-900/80" />
            <div className="space-y-3">
              <div className="h-56 animate-pulse rounded-xl bg-slate-900/80" />
              <div className="h-40 animate-pulse rounded-xl bg-slate-900/80" />
              <div className="h-52 animate-pulse rounded-xl bg-slate-900/80" />
            </div>
          </section>
        ) : null}

        {error ? (
          <section className="rounded-xl border border-red-900/60 bg-red-950/20 p-4 text-sm text-red-200">
            分析失敗：{error.message}
          </section>
        ) : null}

        {data && !error ? (
          <>
            <DashboardMain
              payload={data}
              market={market}
              interval={interval}
              onIntervalChange={setInterval}
            />
            <section className="grid gap-3 xl:grid-cols-3">
              <PatternsPanel candles={data.candle_patterns} charts={data.chart_patterns} />
              <MultiTimeframePanel mtf={data.multi_timeframe} technical={data.technical} />
              <AiPanel
                aiEnabled={data.ai_enabled}
                analysis={data.analysis}
                onEnableHint={() =>
                  setAiHint("請先於設定頁啟用 AI（Phase 10-E 完成串接）。")
                }
              />
            </section>
            {aiHint ? (
              <div className="inline-flex items-center gap-2 rounded-lg border border-amber-800/70 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
                {aiHint}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
