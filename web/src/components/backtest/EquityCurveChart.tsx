"use client";

// Equity curve chart — single or multi-line (Phase 10-E-1)

import { useEffect, useRef } from "react";
import {
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

interface EquitySeries {
  name: string;
  data: Array<{ date: string; value: number }>;
  color?: string;
}

interface EquityCurveChartProps {
  series: EquitySeries[];
  height?: number;
}

const DEFAULT_COLORS = [
  "#60a5fa",
  "#f59e0b",
  "#a78bfa",
  "#34d399",
  "#fb923c",
  "#e879f9",
  "#2dd4bf",
  "#f87171",
];

export function EquityCurveChart({ series, height = 200 }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);

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
      lineSeriesRef.current = [];
    };
  }, [height]);

  useEffect(() => {
    if (!chartRef.current) return;

    // Remove old series
    for (const s of lineSeriesRef.current) {
      chartRef.current.removeSeries(s);
    }
    lineSeriesRef.current = [];

    for (let i = 0; i < series.length; i++) {
      const s = series[i];
      const color = s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
      const lineSeries = chartRef.current.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: s.name,
      });
      const sorted = [...s.data].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
      );
      lineSeries.setData(
        sorted.map((d) => ({ time: d.date as Time, value: d.value })),
      );
      lineSeriesRef.current.push(lineSeries);
    }

    if (series.length > 0 && series[0].data.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [series]);

  return (
    <div data-testid="equity-curve-chart">
      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
