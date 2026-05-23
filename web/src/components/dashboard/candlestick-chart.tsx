"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OhlcvBar, PriceLevel } from "@/types/analysis";
import type { Market } from "@/types/market";
import { MARKET_DOWN_COLOR, MARKET_UP_COLOR } from "@/types/market";
import { formatTwDailyVolume } from "@/lib/formatters";

type ChartInterval = "day" | "week" | "month" | "minute";

interface CandlestickChartProps {
  market: Market;
  interval: ChartInterval;
  daily: OhlcvBar[];
  intraday: OhlcvBar[];
  resistanceLevels?: PriceLevel[];
  supportLevels?: PriceLevel[];
}

export function getPrevCloseColor(currentPrice: number | undefined, previousClose: number | undefined, market: Market): string {
  if (currentPrice == null || previousClose == null) return "#64748b";
  if (currentPrice > previousClose) return MARKET_UP_COLOR[market];
  if (currentPrice < previousClose) return MARKET_DOWN_COLOR[market];
  return "#64748b";
}

interface ChartBar {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface SortableChartBar extends ChartBar {
  sortTs: number;
}

function toDayKey(iso: string): string {
  return iso.slice(0, 10);
}

function toUnixSecond(iso: string): UTCTimestamp | null {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return null;
  return Math.floor(ts / 1000) as UTCTimestamp;
}

function toSortTs(iso: string): number {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return 0;
  return ts;
}

function isoWeekKey(d: Date): string {
  const day = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  day.setUTCDate(day.getUTCDate() + 4 - (day.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(day.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((day.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${day.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function sortRows(rows: OhlcvBar[]): OhlcvBar[] {
  return [...rows].sort(
    (a, b) => toSortTs(a.date) - toSortTs(b.date),
  );
}

function aggregateBars(rows: OhlcvBar[], mode: "week" | "month"): ChartBar[] {
  const sorted = sortRows(rows);
  const buckets = new Map<string, SortableChartBar>();

  for (const row of sorted) {
    const day = new Date(row.date);
    if (Number.isNaN(day.getTime())) continue;
    const sortTs = day.getTime();
    const key =
      mode === "week"
        ? isoWeekKey(day)
        : `${day.getUTCFullYear()}-${String(day.getUTCMonth() + 1).padStart(2, "0")}`;

    const existing = buckets.get(key);
    if (!existing) {
      buckets.set(key, {
        time: toDayKey(row.date),
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close,
        volume: row.volume,
        sortTs,
      });
      continue;
    }
    existing.high = Math.max(existing.high, row.high);
    existing.low = Math.min(existing.low, row.low);
    existing.close = row.close;
    existing.volume += row.volume;
    existing.time = toDayKey(row.date);
    existing.sortTs = sortTs;
  }

  return [...buckets.values()]
    .sort((a, b) => a.sortTs - b.sortTs)
    .map(({ sortTs: _sortTs, ...bar }) => bar);
}

function toChartBars(rows: OhlcvBar[], mode: ChartInterval): ChartBar[] {
  if (mode === "week") return aggregateBars(rows, "week");
  if (mode === "month") return aggregateBars(rows, "month");
  const sorted = sortRows(rows);
  if (mode === "minute") {
    return sorted
      .map((row) => {
        const t = toUnixSecond(row.date);
        if (!t) return null;
        return {
          time: t as Time,
          open: row.open,
          high: row.high,
          low: row.low,
          close: row.close,
          volume: row.volume,
        } satisfies ChartBar;
      })
      .filter((row): row is ChartBar => row !== null);
  }
  return sorted.map((row) => ({
    time: toDayKey(row.date),
    open: row.open,
    high: row.high,
    low: row.low,
    close: row.close,
    volume: row.volume,
  }));
}

function buildSma(rows: ChartBar[], window: number): LineData<Time>[] {
  const out: LineData<Time>[] = [];
  let sum = 0;
  for (let i = 0; i < rows.length; i += 1) {
    sum += rows[i].close;
    if (i >= window) sum -= rows[i - window].close;
    if (i >= window - 1) {
      out.push({ time: rows[i].time, value: Number((sum / window).toFixed(4)) });
    }
  }
  return out;
}

function fmtVol(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}億`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}萬`;
  return String(Math.round(v));
}

const VISIBLE_BARS: Record<ChartInterval, number> = {
  day: 120,
  week: 26,
  month: 12,
  minute: 120,
};

const RIGHT_LABEL_PADDING_BARS: Record<ChartInterval, number> = {
  day: 7,
  week: 2,
  month: 1,
  minute: 7,
};

export function CandlestickChart({
  market,
  interval,
  daily,
  intraday,
  resistanceLevels = [],
  supportLevels = [],
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma5Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma60Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const priceLineRefsRef = useRef<IPriceLine[]>([]);

  // Refs for crosshair tooltip data lookup
  const barsRef = useRef<ChartBar[]>([]);
  const ma5DataRef = useRef<LineData<Time>[]>([]);
  const ma20DataRef = useRef<LineData<Time>[]>([]);
  const ma60DataRef = useRef<LineData<Time>[]>([]);

  const bars = useMemo(() => {
    if (interval === "minute" && intraday.length > 0) return toChartBars(intraday, "minute");
    return toChartBars(daily, interval);
  }, [daily, intraday, interval]);

  useEffect(() => {
    if (!containerRef.current || chartRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      rightPriceScale: { borderVisible: false },
      grid: {
        vertLines: { color: "rgba(100, 116, 139, 0.12)" },
        horzLines: { color: "rgba(100, 116, 139, 0.12)" },
      },
      timeScale: { borderVisible: false },
      crosshair: {
        vertLine: { color: "rgba(148, 163, 184, 0.35)" },
        horzLine: { color: "rgba(148, 163, 184, 0.35)" },
      },
    });

    chart.priceScale("right").applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.30 },
    });

    const upColor = MARKET_UP_COLOR[market];
    const downColor = MARKET_DOWN_COLOR[market];

    const candle = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "vol",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.74, bottom: 0.03 } });

    const ma5 = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const ma20 = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const ma60 = chart.addSeries(LineSeries, {
      color: "#c084fc",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = volume;
    ma5Ref.current = ma5;
    ma20Ref.current = ma20;
    ma60Ref.current = ma60;

    // Crosshair tooltip — created via useEffect to avoid SSR hydration mismatch
    const tooltip = document.createElement("div");
    tooltip.style.cssText = [
      "position:absolute",
      "display:none",
      "padding:8px 10px",
      "background:rgba(15,23,42,0.92)",
      "border:1px solid rgba(100,116,139,0.4)",
      "border-radius:8px",
      "font-size:11px",
      "color:#e2e8f0",
      "pointer-events:none",
      "z-index:10",
      "white-space:nowrap",
      "line-height:1.7",
    ].join(";");
    containerRef.current.appendChild(tooltip);

    chart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time) {
        tooltip.style.display = "none";
        return;
      }
      const bar = barsRef.current.find((b) => b.time === param.time);
      if (!bar) {
        tooltip.style.display = "none";
        return;
      }

      const ma5Val = ma5DataRef.current.find((d) => d.time === param.time)?.value;
      const ma20Val = ma20DataRef.current.find((d) => d.time === param.time)?.value;
      const ma60Val = ma60DataRef.current.find((d) => d.time === param.time)?.value;

      const fmt = (v: number) => v.toFixed(2);
      const volumeText =
        market === "tw" && interval !== "minute"
          ? formatTwDailyVolume(bar.volume)
          : fmtVol(bar.volume);
      const lines = [
        `<span style="color:#94a3b8">${param.time}</span>`,
        `開 <b>${fmt(bar.open)}</b>  高 <b>${fmt(bar.high)}</b>  低 <b>${fmt(bar.low)}</b>  收 <b>${fmt(bar.close)}</b>`,
        `成交量 <b>${volumeText}</b>`,
        [
          ma5Val != null ? `<span style="color:#f59e0b">MA5 ${fmt(ma5Val)}</span>` : "",
          ma20Val != null ? `<span style="color:#3b82f6">MA20 ${fmt(ma20Val)}</span>` : "",
          ma60Val != null ? `<span style="color:#c084fc">MA60 ${fmt(ma60Val)}</span>` : "",
        ].filter(Boolean).join("  "),
      ].filter(Boolean).join("<br>");
      tooltip.innerHTML = lines;

      const container = containerRef.current;
      if (!container) return;
      const containerWidth = container.clientWidth;
      const tooltipWidth = 230;
      const x = param.point.x;
      const left = x + 16 + tooltipWidth < containerWidth ? x + 16 : x - tooltipWidth - 8;
      tooltip.style.display = "block";
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${Math.max(4, param.point.y - 70)}px`;
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
      ma5Ref.current = null;
      ma20Ref.current = null;
      ma60Ref.current = null;
      priceLineRefsRef.current = [];
    };
  }, [market]);

  useEffect(() => {
    if (!candleRef.current || !volRef.current) return;
    const upColor = MARKET_UP_COLOR[market];
    const downColor = MARKET_DOWN_COLOR[market];
    const candleData: CandlestickData<Time>[] = bars.map((row) => ({
      time: row.time,
      open: row.open,
      high: row.high,
      low: row.low,
      close: row.close,
    }));
    const volumeData: HistogramData<Time>[] = bars.map((row) => ({
      time: row.time,
      value: row.volume,
      color: row.close >= row.open ? upColor : downColor,
    }));

    const sma5 = buildSma(bars, 5);
    const sma20 = buildSma(bars, 20);
    const sma60 = buildSma(bars, 60);
    barsRef.current = bars;
    ma5DataRef.current = sma5;
    ma20DataRef.current = sma20;
    ma60DataRef.current = sma60;

    candleRef.current.setData(candleData);
    volRef.current.setData(volumeData);
    ma5Ref.current?.setData(sma5);
    ma20Ref.current?.setData(sma20);
    ma60Ref.current?.setData(sma60);

    // Remove stale S/R lines and redraw
    const candle = candleRef.current;
    for (const pl of priceLineRefsRef.current) {
      try { candle.removePriceLine(pl); } catch { /* ignore if already removed */ }
    }
    priceLineRefsRef.current = [];
    for (const level of resistanceLevels) {
      priceLineRefsRef.current.push(
        candle.createPriceLine({
          price: level.value,
          color: "#ef4444",
          lineStyle: LineStyle.Dashed,
          lineWidth: 1,
          axisLabelVisible: true,
          title: "壓力",
        }),
      );
    }
    for (const level of supportLevels) {
      priceLineRefsRef.current.push(
        candle.createPriceLine({
          price: level.value,
          color: "#22c55e",
          lineStyle: LineStyle.Dashed,
          lineWidth: 1,
          axisLabelVisible: true,
          title: "支撐",
        }),
      );
    }

    // 收盤標籤：顯示最新收盤價，顏色依漲跌
    const lastClose = bars[bars.length - 1]?.close;
    const prevClose = bars[bars.length - 2]?.close;
    if (lastClose != null) {
      const color = getPrevCloseColor(lastClose, prevClose, market);
      priceLineRefsRef.current.push(
        candle.createPriceLine({
          price: lastClose,
          color,
          lineStyle: LineStyle.Dashed,
          lineWidth: 1,
          axisLabelVisible: true,
          title: "收盤",
        }),
      );
    }

    // Set default visible range per interval
    if (bars.length > 0) {
      const visibleCount = VISIBLE_BARS[interval];
      const rightPadding = RIGHT_LABEL_PADDING_BARS[interval];
      chartRef.current?.timeScale().setVisibleLogicalRange({
        from: Math.max(0, bars.length - visibleCount),
        to: bars.length - 1 + rightPadding,
      });
    }
  }, [bars, market, resistanceLevels, supportLevels, interval]);

  return (
    <div
      ref={containerRef}
      className="relative h-[300px] w-full rounded-xl bg-slate-950/70"
      data-testid="candlestick-chart"
    />
  );
}
