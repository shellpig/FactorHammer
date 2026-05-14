"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OhlcvBar } from "@/types/analysis";
import type { Market } from "@/types/market";
import { MARKET_DOWN_COLOR, MARKET_UP_COLOR } from "@/types/market";

type ChartInterval = "day" | "week" | "month" | "minute";

interface CandlestickChartProps {
  market: Market;
  interval: ChartInterval;
  daily: OhlcvBar[];
  intraday: OhlcvBar[];
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

function buildRsi(rows: ChartBar[], period = 14): LineData<Time>[] {
  if (rows.length <= period) return [];
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i += 1) {
    const diff = rows[i].close - rows[i - 1].close;
    avgGain += diff > 0 ? diff : 0;
    avgLoss += diff < 0 ? Math.abs(diff) : 0;
  }
  avgGain /= period;
  avgLoss /= period;

  const out: LineData<Time>[] = [];
  const firstRs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  out.push({
    time: rows[period].time,
    value: Number((100 - 100 / (1 + firstRs)).toFixed(4)),
  });

  for (let i = period + 1; i < rows.length; i += 1) {
    const diff = rows[i].close - rows[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    out.push({
      time: rows[i].time,
      value: Number((100 - 100 / (1 + rs)).toFixed(4)),
    });
  }
  return out;
}

function buildStochasticKD(
  rows: ChartBar[],
  period = 9,
): { k: LineData<Time>[]; d: LineData<Time>[] } {
  if (rows.length < period) return { k: [], d: [] };
  const kData: LineData<Time>[] = [];
  const dData: LineData<Time>[] = [];
  let kPrev = 50;
  let dPrev = 50;

  for (let i = period - 1; i < rows.length; i += 1) {
    const window = rows.slice(i - period + 1, i + 1);
    const highest = Math.max(...window.map((row) => row.high));
    const lowest = Math.min(...window.map((row) => row.low));
    const close = rows[i].close;
    const rsv = highest === lowest ? 50 : ((close - lowest) / (highest - lowest)) * 100;
    const k = (2 / 3) * kPrev + (1 / 3) * rsv;
    const d = (2 / 3) * dPrev + (1 / 3) * k;
    kPrev = k;
    dPrev = d;
    kData.push({ time: rows[i].time, value: Number(k.toFixed(4)) });
    dData.push({ time: rows[i].time, value: Number(d.toFixed(4)) });
  }
  return { k: kData, d: dData };
}

function buildEma(values: number[], period: number): number[] {
  if (values.length === 0) return [];
  const out: number[] = [values[0]];
  const alpha = 2 / (period + 1);
  for (let i = 1; i < values.length; i += 1) {
    out.push(values[i] * alpha + out[i - 1] * (1 - alpha));
  }
  return out;
}

function buildMacd(
  rows: ChartBar[],
): { macd: LineData<Time>[]; signal: LineData<Time>[]; hist: HistogramData<Time>[] } {
  if (rows.length < 26) return { macd: [], signal: [], hist: [] };
  const closes = rows.map((row) => row.close);
  const ema12 = buildEma(closes, 12);
  const ema26 = buildEma(closes, 26);
  const macdValues = closes.map((_, idx) => ema12[idx] - ema26[idx]);
  const signalValues = buildEma(macdValues, 9);
  const macd: LineData<Time>[] = [];
  const signal: LineData<Time>[] = [];
  const hist: HistogramData<Time>[] = [];

  for (let i = 0; i < rows.length; i += 1) {
    const m = macdValues[i];
    const s = signalValues[i];
    const h = m - s;
    macd.push({ time: rows[i].time, value: Number(m.toFixed(4)) });
    signal.push({ time: rows[i].time, value: Number(s.toFixed(4)) });
    hist.push({
      time: rows[i].time,
      value: Number(h.toFixed(4)),
      color: h >= 0 ? "rgba(239, 68, 68, 0.8)" : "rgba(34, 197, 94, 0.8)",
    });
  }
  return { macd, signal, hist };
}

export function CandlestickChart({
  market,
  interval,
  daily,
  intraday,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma5Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma60Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const kdKRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdDRef = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const bars = useMemo(() => {
    if (interval === "minute" && intraday.length > 0) return toChartBars(intraday, "minute");
    return toChartBars(daily, interval);
  }, [daily, intraday, interval]);

  useEffect(() => {
    if (!containerRef.current || chartRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 620,
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
      scaleMargins: { top: 0.05, bottom: 0.52 },
    });

    const upColor = MARKET_UP_COLOR[market];
    const downColor = MARKET_DOWN_COLOR[market];

    const candle = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      borderVisible: false,
    });

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "vol",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.56, bottom: 0.34 } });

    const ma5 = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const ma20 = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const ma60 = chart.addSeries(LineSeries, {
      color: "#c084fc",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const kdK = chart.addSeries(LineSeries, {
      priceScaleId: "kd",
      color: "#fb923c",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const kdD = chart.addSeries(LineSeries, {
      priceScaleId: "kd",
      color: "#60a5fa",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    kdK.priceScale().applyOptions({ scaleMargins: { top: 0.69, bottom: 0.22 } });

    const rsi = chart.addSeries(LineSeries, {
      priceScaleId: "rsi",
      color: "#f472b6",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    rsi.priceScale().applyOptions({ scaleMargins: { top: 0.80, bottom: 0.11 } });

    const macd = chart.addSeries(LineSeries, {
      priceScaleId: "macd",
      color: "#a78bfa",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const macdSignal = chart.addSeries(LineSeries, {
      priceScaleId: "macd",
      color: "#fbbf24",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const macdHist = chart.addSeries(HistogramSeries, {
      priceScaleId: "macd",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    macd.priceScale().applyOptions({ scaleMargins: { top: 0.89, bottom: 0.01 } });

    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = volume;
    ma5Ref.current = ma5;
    ma20Ref.current = ma20;
    ma60Ref.current = ma60;
    kdKRef.current = kdK;
    kdDRef.current = kdD;
    rsiRef.current = rsi;
    macdRef.current = macd;
    macdSignalRef.current = macdSignal;
    macdHistRef.current = macdHist;

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
      ma5Ref.current = null;
      ma20Ref.current = null;
      ma60Ref.current = null;
      kdKRef.current = null;
      kdDRef.current = null;
      rsiRef.current = null;
      macdRef.current = null;
      macdSignalRef.current = null;
      macdHistRef.current = null;
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
    const kd = buildStochasticKD(bars);
    const rsi = buildRsi(bars, 14);
    const macd = buildMacd(bars);

    candleRef.current.setData(candleData);
    volRef.current.setData(volumeData);
    ma5Ref.current?.setData(buildSma(bars, 5));
    ma20Ref.current?.setData(buildSma(bars, 20));
    ma60Ref.current?.setData(buildSma(bars, 60));
    kdKRef.current?.setData(kd.k);
    kdDRef.current?.setData(kd.d);
    rsiRef.current?.setData(rsi);
    macdRef.current?.setData(macd.macd);
    macdSignalRef.current?.setData(macd.signal);
    macdHistRef.current?.setData(macd.hist);
    chartRef.current?.timeScale().fitContent();
  }, [bars, market]);

  return (
    <div
      ref={containerRef}
      className="h-[620px] w-full rounded-xl bg-slate-950/70"
      data-testid="candlestick-chart"
    />
  );
}
