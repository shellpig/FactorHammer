"use client";

// K-line chart with buy/sell markers and optional MA overlay (Phase 10-E-1)

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { MARKET_DOWN_COLOR, MARKET_UP_COLOR } from "@/types/market";
import type { Market } from "@/types/market";

interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Signal {
  date: string;
  side: "buy" | "sell";
  price: number;
}

interface MaOverlay {
  name: string;
  period: number;
  color: string;
}

interface CandleChartWithMarkersProps {
  priceData: PriceBar[];
  signals: Signal[];
  market: Market;
  maOverlay?: MaOverlay[];
  height?: number;
}

const MA_COLORS = ["#60a5fa", "#f59e0b", "#a78bfa", "#34d399"];

function calcMA(data: PriceBar[], period: number): { time: Time; value: number }[] {
  const result: { time: Time; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const avg = slice.reduce((s, b) => s + b.close, 0) / period;
    result.push({ time: data[i].date as Time, value: avg });
  }
  return result;
}

export function CandleChartWithMarkers({
  priceData,
  signals,
  market,
  maOverlay = [],
  height = 400,
}: CandleChartWithMarkersProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const maSeriesRef = useRef<ISeriesApi<"Line">[]>([]);

  const upColor = MARKET_UP_COLOR[market];
  const downColor = MARKET_DOWN_COLOR[market];

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(100,116,139,0.15)" },
        horzLines: { color: "rgba(100,116,139,0.15)" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "rgba(100,116,139,0.3)" },
      timeScale: {
        borderColor: "rgba(100,116,139,0.3)",
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height,
    });
    chartRef.current = chart;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      priceLineVisible: false,
    });
    candleRef.current = candle;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      markersRef.current = null;
      maSeriesRef.current = [];
    };
  }, [upColor, downColor, height]);

  // Update candlestick data + markers
  useEffect(() => {
    if (!candleRef.current || !chartRef.current) return;

    const sorted = [...priceData].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );
    const bars = sorted.map((b) => ({
      time: b.date as Time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    candleRef.current.setData(bars);

    // markers — v5 API: createSeriesMarkers(series, markers)
    const markers: SeriesMarker<Time>[] = signals
      .filter((s) => sorted.some((b) => b.date === s.date))
      .map((s) => ({
        time: s.date as Time,
        position: s.side === "buy" ? "belowBar" : "aboveBar",
        color: s.side === "buy" ? upColor : downColor,
        shape: s.side === "buy" ? "arrowUp" : "arrowDown",
        text: s.side === "buy" ? "B" : "S",
      }));
    if (markersRef.current) {
      markersRef.current.setMarkers(markers);
    } else {
      markersRef.current = createSeriesMarkers(candleRef.current, markers);
    }

    // default visible range: last 6 months
    if (sorted.length > 0) {
      const last = new Date(sorted[sorted.length - 1].date);
      const sixMonthsAgo = new Date(last);
      sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
      const fromIdx = sorted.findIndex((b) => new Date(b.date) >= sixMonthsAgo);
      const from = Math.max(0, fromIdx);
      chartRef.current.timeScale().setVisibleLogicalRange({
        from: Math.max(0, from - 0.5),
        to: sorted.length - 0.5,
      });
    }
  }, [priceData, signals, upColor, downColor]);

  // MA overlays
  useEffect(() => {
    if (!chartRef.current) return;
    // Remove old MA series
    for (const s of maSeriesRef.current) {
      chartRef.current.removeSeries(s);
    }
    maSeriesRef.current = [];

    for (let i = 0; i < maOverlay.length; i++) {
      const ov = maOverlay[i];
      const color = ov.color || MA_COLORS[i % MA_COLORS.length];
      const maSeries = chartRef.current.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: ov.name,
      });
      const sorted = [...priceData].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
      );
      maSeries.setData(calcMA(sorted, ov.period));
      maSeriesRef.current.push(maSeries);
    }
  }, [priceData, maOverlay]);

  return (
    <div data-testid="candle-chart-with-markers">
      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
