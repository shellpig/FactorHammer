"use client";

import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { RefreshCw, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { mutate as mutateGlobal } from "swr";
import { MarketSwitcher } from "@/components/market-switcher";
import { StockSelector } from "@/components/stock-selector";
import { CandlestickChart } from "@/components/dashboard/candlestick-chart";
import { HelpTooltip } from "@/components/dashboard/help-tooltip";
import { DividendHistoryPanel } from "@/components/dashboard/p11/dividend-history-panel";
import { EventCalendarPanel } from "@/components/dashboard/p11/event-calendar-panel";
import { IndustryPerModal } from "@/components/dashboard/p11/industry-per-modal";
import { InstitutionalCostPanel } from "@/components/dashboard/p11/institutional-cost-panel";
import { MonthlyRevenuePanel } from "@/components/dashboard/p11/monthly-revenue-panel";
import { ShareholderMeetingEditDialog } from "@/components/dashboard/p11/shareholder-meeting-edit-dialog";
import { TokenSetupDialog } from "@/components/dashboard/token-setup-dialog";
import { ValuationPanel } from "@/components/dashboard/p11/valuation-panel";
import {
  DASHBOARD_TOOLTIP_TEXT,
  PATTERN_DETAILS,
} from "@/components/dashboard/tooltip-text";
import { apiGet } from "@/lib/api-client";
import { useP11DividendHistory } from "@/lib/hooks/useP11DividendHistory";
import { useP11EventCalendar } from "@/lib/hooks/useP11EventCalendar";
import { useP11IndustryPer } from "@/lib/hooks/useP11IndustryPer";
import { useP11InstitutionalCost } from "@/lib/hooks/useP11InstitutionalCost";
import { useP11MonthlyRevenue } from "@/lib/hooks/useP11MonthlyRevenue";
import { useP11Valuation } from "@/lib/hooks/useP11Valuation";
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

const LS_SYMBOL = "qt-last-symbol";
const LS_MARKET = "qt-last-market";
const BACKEND_HEALTH_RETRY_INTERVAL_MS = 1000;
const BACKEND_HEALTH_TIMEOUT_MS = 60_000;

function readLastSymbol(): string {
  try {
    return localStorage.getItem(LS_SYMBOL) ?? "2330";
  } catch {
    return "2330";
  }
}

function readLastMarket(): Market {
  try {
    const v = localStorage.getItem(LS_MARKET);
    return v === "us" ? "us" : "tw";
  } catch {
    return "tw";
  }
}

function renderRatio(ratio: number): string {
  return `${(ratio * 100).toFixed(2)}%`;
}

function StartupOverlay({
  timedOut,
  onRetry,
}: {
  timedOut: boolean;
  onRetry: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/92 p-6"
      data-testid="startup-overlay"
    >
      <section className="w-full max-w-xl rounded-xl border border-slate-700 bg-slate-900/90 p-6 text-center">
        <h2 className="text-lg font-semibold text-slate-100">工具初始化中...</h2>
        {!timedOut ? (
          <p className="mt-3 text-sm text-slate-300">
            正在啟動後端服務，完成後會自動進入分析頁面。
          </p>
        ) : (
          <>
            <p className="mt-3 text-sm text-amber-200">
              後端啟動逾時，請確認 FactorHammer-Backend-8000 視窗是否有錯誤。
            </p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex items-center rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-800"
            >
              重新檢查
            </button>
          </>
        )}
      </section>
    </div>
  );
}

function twTickSize(price: number): number {
  if (price < 10) return 0.01;
  if (price < 50) return 0.05;
  if (price < 100) return 0.1;
  if (price < 500) return 0.5;
  if (price < 1000) return 1;
  return 5;
}

function formatLevelPrice(value: number, market: Market): string {
  if (market === "us") return formatNumber(value, 2);
  const tick = twTickSize(value);
  if (tick >= 1) return formatNumber(value, 0);
  if (tick >= 0.1) return formatNumber(value, 1);
  return formatNumber(value, 2);
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
      <section className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-2 text-xs text-slate-300" data-testid="quote-header-row">
        <span className="text-slate-500">Price</span>{"　"}
        <span className="[font-family:var(--font-mono)] text-slate-100">{formatNumber(intradaySnapshot.price, 2)}</span>
        {"　　"}
        <span className="text-slate-500">前收</span>{"　"}
        <span className="[font-family:var(--font-mono)] text-slate-100">{formatNumber(intradaySnapshot.previous_raw_close, 2)}</span>
        {"　　"}
        <span className="text-slate-500">Change</span>{"　"}
        <span className={`[font-family:var(--font-mono)] ${changeColor(intradaySnapshot.change, market)}`}>
          {formatSignedValue(intradaySnapshot.change, 2)} ({formatPct(intradaySnapshot.change_pct, 2)})
        </span>
        {"　　"}
        <span className="text-slate-500">成交量</span>{"　"}
        <span className="[font-family:var(--font-mono)] text-slate-100">{formatNumber(intradaySnapshot.volume, 0)}</span>
      </section>
    );
  }
  if (!quote) return null;
  const isMarketOpen = quote.is_market_open;
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-2 text-xs text-slate-300" data-testid="quote-header-row">
      <span className="text-slate-500">開盤</span>{"　"}
      <span className="[font-family:var(--font-mono)]">{formatNumber(quote.open, 2)}</span>
      {"　　"}
      <span className="text-slate-500">最高</span>{"　"}
      <span className="[font-family:var(--font-mono)]">{formatNumber(quote.high, 2)}</span>
      {"　　"}
      <span className="text-slate-500">最低</span>{"　"}
      <span className="[font-family:var(--font-mono)]">{formatNumber(quote.low, 2)}</span>
      {"　　"}
      <span className="text-slate-500">前收</span>{"　"}
      <span className="[font-family:var(--font-mono)]">{formatNumber(quote.yesterday_close, 2)}</span>
      {"　　"}
      <span className="text-slate-500">成交量</span>{"　"}
      <span className="[font-family:var(--font-mono)]">{formatNumber(quote.volume, 0)}</span>
      {isMarketOpen ? (
        <>
          {"　　"}
          <span className="text-slate-500">買量</span>{"　"}
          <span className={`[font-family:var(--font-mono)] ${changeColor(1, "tw")}`}>
            {formatNumber((quote.best_bid_vol?.[0] ?? 0) + (quote.best_bid_vol?.[1] ?? 0), 0)}
          </span>
          {"　　"}
          <span className="text-slate-500">賣量</span>{"　"}
          <span className={`[font-family:var(--font-mono)] ${changeColor(-1, "tw")}`}>
            {formatNumber((quote.best_ask_vol?.[0] ?? 0) + (quote.best_ask_vol?.[1] ?? 0), 0)}
          </span>
        </>
      ) : null}
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
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">技術分析總覽</h3>
        <span className="text-xs text-slate-500">近 60 日</span>
      </div>
      <div className="space-y-1">
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-[80px_1fr] items-start gap-1.5 border-b border-slate-800/70 pb-1 text-xs"
          >
            <div className="flex items-center gap-1 text-slate-300">
              {row.label}
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT[row.key]} />
            </div>
            <div className="min-w-0 break-words [font-family:var(--font-mono)] text-slate-100">{row.value}</div>
          </div>
        ))}
        <div className="grid grid-cols-[80px_1fr] items-start gap-1.5 pt-1 text-xs">
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

function LevelsPanel({
  technical,
  market,
}: {
  technical: TechnicalSummary;
  market: Market;
}) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">關鍵價位</h3>
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex shrink-0 items-center gap-1 text-xs text-slate-400">
            壓力區
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.resistance} />
          </div>
          <div className="min-w-0 text-right text-base font-semibold text-rise [font-family:var(--font-mono)]">
            {technical.resistance_levels
              .map((item) => formatLevelPrice(item.value, market))
              .join(" / ")}
          </div>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex shrink-0 items-center gap-1 text-xs text-slate-400">
            支撐區
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.support} />
          </div>
          <div className="min-w-0 text-right text-base font-semibold text-fall [font-family:var(--font-mono)]">
            {technical.support_levels
              .map((item) => formatLevelPrice(item.value, market))
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
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">籌碼分析 近 5 日</h3>
        {chipRecent.length > 0 ? <ChipRecentDialog rows={chipRecent} /> : null}
      </div>

      {bidAsk ? (
        <div className="mb-2 rounded-lg border border-slate-800 bg-slate-900/60 p-2">
          <div className="flex items-center justify-between gap-2 text-xs" data-testid="chip-bid-ask-inline">
            <div className="flex shrink-0 items-center gap-1 text-slate-300">
              買賣力道
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.bid_ask} />
            </div>
            <div className="min-w-0 text-right [font-family:var(--font-mono)]">
              <span className="text-slate-100">{bidAsk.label}</span>
              <span className="ml-2 whitespace-nowrap text-slate-400">
                買方 {renderRatio(bidAsk.bid_ratio)} / 賣方 {renderRatio(bidAsk.ask_ratio)}
              </span>
            </div>
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

      <div className="my-2 rounded-lg border border-slate-800 bg-slate-900/40 p-2 text-xs">
        <div className="flex items-center gap-6" data-testid="chip-financing-inline-row">
          <div
            className="flex items-center gap-1 whitespace-nowrap text-slate-400"
            data-testid="chip-margin-inline"
          >
            <span className="inline-flex items-center gap-1">
              融資
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.margin_balance} />
            </span>
            <span className={`[font-family:var(--font-mono)] ${changeColor(chip.margin_balance_change, "tw")}`}>
              {formatSignedValue(chip.margin_balance_change, 0)} 張
            </span>
          </div>
          <div
            className="flex items-center gap-1 whitespace-nowrap text-slate-400"
            data-testid="chip-short-inline"
          >
            <span className="inline-flex items-center gap-1">
              融券
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.short_balance} />
            </span>
            <span className={`[font-family:var(--font-mono)] ${changeColor(chip.short_balance_change, "tw")}`}>
              {formatSignedValue(chip.short_balance_change, 0)} 張
            </span>
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
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">K 線型態</h3>
      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-xs">
          <thead className="bg-slate-900/80 text-slate-300">
            <tr>
              <th className="px-2 py-1.5 text-left">型態</th>
              <th className="w-14 px-2 py-1.5 text-left">狀態</th>
              <th className="px-2 py-1.5 text-left">說明</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-t border-slate-800">
                <td className="min-w-0 px-2 py-1.5">
                  <span className="flex items-center gap-1 break-all">
                    {row.name}
                    {PATTERN_DETAILS[row.name] ? (
                      <HelpTooltip text={PATTERN_DETAILS[row.name] ?? ""} />
                    ) : null}
                  </span>
                </td>
                <td className="px-2 py-1.5">
                  <span
                    className={`whitespace-nowrap rounded-full px-1.5 py-0.5 text-xs ${
                      row.formed
                        ? "bg-rise/15 text-rise"
                        : "bg-slate-700/60 text-slate-300"
                    }`}
                  >
                    {row.formed ? "成立" : "未成"}
                  </span>
                </td>
                <td className="min-w-0 break-words px-2 py-1.5 text-slate-300">{row.description}</td>
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
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">多週期 · 量價</h3>
      <div className="space-y-1.5 border-b border-slate-800 pb-2">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[46px_64px_1fr] items-center gap-1.5 text-xs">
            <div className="flex items-center gap-1 text-slate-300">
              {row.label}
              <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT[row.key]} />
            </div>
            <span className="rounded-full bg-rise/15 px-1.5 py-0.5 text-center text-rise">
              {row.value.trend_direction}
            </span>
            <span className="min-w-0 break-words text-slate-100 [font-family:var(--font-mono)]">{row.value.strength}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 space-y-2">
        <div>
          <div className="mb-0.5 flex items-center gap-1 text-xs text-slate-300">
            量價背離
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.volume_price_divergence} />
          </div>
          <p className="break-words text-xs text-slate-100">{technical.volume_price_divergence}</p>
        </div>
        <div>
          <div className="mb-0.5 flex items-center gap-1 text-xs text-slate-300">
            均線乖離
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.ma_bias} />
          </div>
          <p className="break-words text-xs text-slate-100">{technical.ma_bias}</p>
        </div>
        <div>
          <div className="mb-0.5 flex items-center gap-1 text-xs text-slate-300">
            操作觀察
            <HelpTooltip text={DASHBOARD_TOOLTIP_TEXT.operation_observation} />
          </div>
          <p className="break-words text-xs text-slate-100">{technical.operation_observation}</p>
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
      <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
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
      <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">隔日操作劇本</h3>
        <p className="text-sm text-slate-300">AI 分析失敗，請稍後重試。</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-200">隔日操作劇本</h3>
      <div className="space-y-1.5">
        {analysis.scenarios.map((scenario) => (
          <div key={scenario.name} className="rounded-lg border border-slate-800 bg-slate-900/40 p-2">
            <div className="mb-1 text-xs font-medium text-slate-100">{scenario.name}</div>
            <div className="grid grid-cols-3 gap-1 text-xs text-slate-300">
              <div>
                <div className="text-slate-500">進場價</div>
                <div className="break-all [font-family:var(--font-mono)]">{scenario.entry_range}</div>
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
      <p className="mt-2 text-xs text-slate-400">{analysis.conclusion}</p>
    </section>
  );
}

function ChartSection({
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
    <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
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
        <div className="flex items-center gap-2 text-xs">
          <span style={{ color: "#f59e0b" }}>MA5</span>
          <span style={{ color: "#3b82f6" }}>MA20</span>
          <span style={{ color: "#c084fc" }}>MA60</span>
        </div>
      </div>
      <CandlestickChart
        market={market}
        interval={interval}
        daily={payload.daily_df}
        intraday={payload.intraday_df}
        resistanceLevels={payload.technical.resistance_levels}
        supportLevels={payload.technical.support_levels}
      />
    </section>
  );
}

export default function DashboardPageClient() {
  const router = useRouter();
  // SSR-safe defaults: localStorage is only available on the client.
  // Do NOT read localStorage in useState initializers — it causes hydration mismatch.
  const [market, setMarket] = useState<Market>("tw");
  const [pendingSymbol, setPendingSymbol] = useState("2330");
  const [symbol, setSymbol] = useState<string | null>(null);
  const [interval, setInterval] = useState<ChartInterval>("day");
  const [aiHint, setAiHint] = useState<string>("");
  const [industryModalOpen, setIndustryModalOpen] = useState(false);
  const [shareholderDialogOpen, setShareholderDialogOpen] = useState(false);
  const [tokenSetupOpen, setTokenSetupOpen] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [backendTimedOut, setBackendTimedOut] = useState(false);
  const [backendProbeSeed, setBackendProbeSeed] = useState(0);
  // Gate dashboard fetch on secrets/status: do not fire useDashboard until we know
  // FinMind is configured (or user completed token setup).
  // Without this, the dashboard fetch races the modal and the user briefly sees
  // a fetch error before the forced token-setup modal appears.
  const [secretsChecked, setSecretsChecked] = useState(false);
  const [finmindReady, setFinmindReady] = useState(false);

  useEffect(() => {
    if (backendReady) return;
    let cancelled = false;
    const maxAttempts = Math.max(
      1,
      Math.ceil(BACKEND_HEALTH_TIMEOUT_MS / BACKEND_HEALTH_RETRY_INTERVAL_MS),
    );
    void (async () => {
      for (let i = 0; i < maxAttempts; i++) {
        try {
          await apiGet<{ status: string }>("/api/health");
          if (cancelled) return;
          setBackendTimedOut(false);
          setBackendReady(true);
          return;
        } catch {
          if (cancelled) return;
          if (i < maxAttempts - 1) {
            await new Promise<void>((resolve) =>
              setTimeout(resolve, BACKEND_HEALTH_RETRY_INTERVAL_MS),
            );
          }
        }
      }
      if (!cancelled) setBackendTimedOut(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [backendReady, backendProbeSeed]);

  useEffect(() => {
    if (!backendReady || secretsChecked) return;
    let cancelled = false;
    void (async () => {
      for (let i = 0; i < 5; i++) {
        try {
          const status = await apiGet<Record<string, boolean>>("/api/config/secrets/status");
          if (cancelled) return;
          if (status.data.finmind) setFinmindReady(true);
          else setTokenSetupOpen(true);
          setSecretsChecked(true);
          return;
        } catch {
          if (cancelled) return;
          if (i < 4) {
            await new Promise<void>((r) => setTimeout(r, 1000));
            continue;
          }
          // 5 retries exhausted — force modal; do not degrade to finmindReady=true
          setTokenSetupOpen(true);
          setSecretsChecked(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [backendReady, secretsChecked]);

  // Restore last selection UI immediately so market switcher / input reflect history.
  useEffect(() => {
    const savedMarket = readLastMarket();
    const savedSymbol = readLastSymbol();
    setMarket(savedMarket);
    setPendingSymbol(savedSymbol);
  }, []);

  // Trigger the initial dashboard fetch only after the secrets check completes.
  useEffect(() => {
    if (!secretsChecked || !finmindReady) return;
    if (symbol !== null) return;
    setSymbol(readLastSymbol());
  }, [secretsChecked, finmindReady, symbol]);

  useEffect(() => {
    if (symbol) localStorage.setItem(LS_SYMBOL, symbol);
  }, [symbol]);

  useEffect(() => {
    localStorage.setItem(LS_MARKET, market);
  }, [market]);

  const { data, error, isLoading, mutate } = useDashboard(symbol, market);
  // Gate P11 hooks on dashboard payload being ready: build_dashboard_payload writes
  // daily/dividends/per/eps/monthly_revenue/institutional/margin parquets, so P11
  // endpoints would race and read empty files on first visit otherwise.
  const p11Ready = !!data && !error;
  const { data: valuation } = useP11Valuation(symbol, market, p11Ready);
  const { data: monthlyRevenue } = useP11MonthlyRevenue(symbol, market, 12, p11Ready);
  const { data: dividendHistory } = useP11DividendHistory(symbol, market, 5, p11Ready);
  const { data: institutionalCost } = useP11InstitutionalCost(symbol, market, 30, p11Ready);
  const { data: eventCalendar, mutate: mutateEventCalendar } = useP11EventCalendar(symbol, market, p11Ready);
  const { data: industryPer, isLoading: industryPerLoading } = useP11IndustryPer(
    symbol,
    market,
    industryModalOpen,
  );
  const currentShareholderMeeting =
    eventCalendar?.next_shareholder_meeting ?? eventCalendar?.last_shareholder_meeting ?? null;

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

  function handleRetryBackendStartup() {
    setBackendTimedOut(false);
    setBackendProbeSeed((prev) => prev + 1);
  }

  return (
    <div className="-mx-4 -my-6 px-4 py-6 xl:px-6">
      <div className="mx-auto max-w-[2400px]">
        {/* Three-column layout: left=chart(50%), middle=analysis(25%), right=patterns(25%) */}
        <div className="xl:grid xl:grid-cols-[2fr_1fr_1fr] xl:gap-3 xl:items-start">

          {/* ── Left column ── */}
          <div className="space-y-3">
            {/* Compact header — no title, single control row + price row */}
            <header className="space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3">
              {/* Control row */}
              <div className="flex flex-wrap items-center gap-2">
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
                  className="w-32 min-w-0"
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

              {/* Price row */}
              <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-2">
                <div className="text-xl font-semibold [font-family:var(--font-mono)] text-slate-100">
                  {titleSymbol}
                </div>
                <div className="text-base text-slate-200">{titleName}</div>
                {quote || intradaySnapshot ? (
                  <>
                    <div className={`text-3xl font-semibold [font-family:var(--font-mono)] ${priceTone}`}>
                      {formatNumber(quote?.price ?? intradaySnapshot?.price ?? 0, 2)}
                    </div>
                    <div className={`text-base [font-family:var(--font-mono)] ${priceTone}`}>
                      {formatSignedValue(quote?.change ?? intradaySnapshot?.change ?? 0, 2)} (
                      {formatPct(quote?.change_pct ?? intradaySnapshot?.change_pct ?? 0, 2)})
                    </div>
                    <div className="text-xs text-slate-500">
                      {data?.analysis_time} · {interval === "minute" ? "分 K" : "日 K"}
                    </div>
                  </>
                ) : (
                  <div className="text-xs text-slate-500">美股模式暫無即時報價</div>
                )}
              </div>
            </header>

            {!symbol ? (
              <section className="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-8 text-center text-slate-400">
                請輸入股票代碼或名稱後點選「分析」。
              </section>
            ) : null}

            {isLoading ? (
              <div
                className="h-[300px] animate-pulse rounded-xl bg-slate-900/80"
                data-testid="dashboard-chart-skeleton"
              />
            ) : null}

            {error ? (
              <section className="rounded-xl border border-red-900/60 bg-red-950/20 p-4 text-sm text-red-200">
                分析失敗：{error.message}
              </section>
            ) : null}

            {data && !error ? (
              <>
                <HeaderRow
                  quote={data.quote}
                  intradaySnapshot={data.intraday_snapshot}
                  market={market}
                />
                <ChartSection
                  payload={data}
                  market={market}
                  interval={interval}
                  onIntervalChange={setInterval}
                />
                {market === "tw" ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-3" data-testid="p11-grid-left">
                      <ValuationPanel data={valuation} onOpenIndustry={() => setIndustryModalOpen(true)} />
                      <MonthlyRevenuePanel data={monthlyRevenue} />
                      <DividendHistoryPanel data={dividendHistory} />
                    </div>
                    <div
                      className="space-y-3"
                      data-testid="p11-grid-right"
                    >
                      <InstitutionalCostPanel data={institutionalCost} />
                      <EventCalendarPanel
                        data={eventCalendar}
                        onEdit={() => setShareholderDialogOpen(true)}
                      />
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          {/* ── Middle column: analysis panels ── */}
          {data && !error ? (
            <div className="mt-3 space-y-2 xl:mt-0">
              <TechnicalPanel technical={data.technical} />
              <LevelsPanel technical={data.technical} market={market} />
              {market === "tw" ? (
                <ChipPanel
                  chip={data.chip}
                  bidAsk={data.bid_ask}
                  chipRecent={data.chip_recent_df}
                />
              ) : null}
              <AiPanel
                aiEnabled={data.ai_enabled}
                analysis={data.analysis}
                onEnableHint={() =>
                  setAiHint("請先於設定頁啟用 AI（Phase 10-E 完成串接）。")
                }
              />
            </div>
          ) : null}

          {/* ── Right column: pattern panels ── */}
          {data && !error ? (
            <div className="mt-3 space-y-2 xl:mt-0">
              <PatternsPanel candles={data.candle_patterns} charts={data.chart_patterns} />
              <MultiTimeframePanel mtf={data.multi_timeframe} technical={data.technical} />
            </div>
          ) : null}
        </div>

        {aiHint ? (
          <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-amber-800/70 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
            {aiHint}
          </div>
        ) : null}
      </div>
      <IndustryPerModal
        open={industryModalOpen}
        onOpenChange={setIndustryModalOpen}
        data={industryPer}
        isLoading={industryPerLoading}
      />
      <ShareholderMeetingEditDialog
        open={shareholderDialogOpen}
        onOpenChange={setShareholderDialogOpen}
        symbol={symbol ?? ""}
        market={market}
        current={currentShareholderMeeting}
        onSaved={async () => {
          await mutateEventCalendar();
        }}
      />
      <TokenSetupDialog
        open={tokenSetupOpen && backendReady}
        onSaved={async () => {
          setTokenSetupOpen(false);
          setFinmindReady(true);
          await mutateGlobal(() => true, undefined, { revalidate: true });
          router.refresh();
        }}
      />
      {!backendReady ? (
        <StartupOverlay timedOut={backendTimedOut} onRetry={handleRetryBackendStartup} />
      ) : null}
    </div>
  );
}
