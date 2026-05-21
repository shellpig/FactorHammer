"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { BacktestBatchSummary } from "./batch-types";

export const STRATEGY_COLORS = [
  "#3b82f6",
  "#ef4444",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
];

interface MultiEquityChartProps {
  summaries: BacktestBatchSummary[];
  height?: number;
}

interface TooltipState {
  x: number;
  y: number;
  date: string;
  rows: Array<{ name: string; value: number; color: string }>;
}

function normalizeTime(time: Time): string | null {
  if (typeof time === "string") return time;
  if (typeof time === "number") {
    return new Date(time * 1000).toISOString().slice(0, 10);
  }
  if (time && typeof time === "object" && "year" in time && "month" in time && "day" in time) {
    const y = String(time.year).padStart(4, "0");
    const m = String(time.month).padStart(2, "0");
    const d = String(time.day).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }
  return null;
}

export function MultiEquityChart({ summaries, height = 520 }: MultiEquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineRefs = useRef<Array<ISeriesApi<"Line">>>([]);
  const lineMetaRef = useRef<Array<{
    series: ISeriesApi<"Line">;
    name: string;
    color: string;
    valueByDate: Map<string, number>;
  }>>([]);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const lines = useMemo(() => {
    return summaries
      .filter((s) => !s.error && s.detail && s.detail.equity_curve.length > 0)
      .map((s, i) => ({
        name: s.preset_name,
        color: STRATEGY_COLORS[i % STRATEGY_COLORS.length],
        data: s.detail!.equity_curve,
      }));
  }, [summaries]);

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
      rightPriceScale: { borderColor: "rgba(100,116,139,0.3)" },
      timeScale: { borderColor: "rgba(100,116,139,0.3)", timeVisible: true, secondsVisible: false },
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
      lineRefs.current = [];
      lineMetaRef.current = [];
    };
  }, [height]);

  useEffect(() => {
    if (!chartRef.current) return;
    for (const s of lineRefs.current) {
      chartRef.current.removeSeries(s);
    }
    lineRefs.current = [];
    lineMetaRef.current = [];
    setTooltip(null);

    for (const line of lines) {
      const series = chartRef.current.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: line.name,
      });
      series.setData(
        [...line.data]
          .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
          .map((d) => ({ time: d.date as Time, value: d.value })),
      );
      lineRefs.current.push(series);
      lineMetaRef.current.push({
        series,
        name: line.name,
        color: line.color,
        valueByDate: new Map(line.data.map((d) => [d.date, d.value])),
      });
    }

    if (lines.length > 0) {
      chartRef.current.timeScale().fitContent();
    }

    const handler = (param: any) => {
      if (!containerRef.current || !param?.point || !param?.time) {
        setTooltip(null);
        return;
      }

      const date = normalizeTime(param.time as Time);
      if (!date) {
        setTooltip(null);
        return;
      }

      const width = containerRef.current.clientWidth;
      const maxX = Math.max(0, width - 220);
      const x = Math.min(Math.max(param.point.x + 12, 8), maxX);
      const y = Math.max(param.point.y - 12, 8);

      const rows = lineMetaRef.current
        .map((meta) => {
          const seriesValue = param.seriesData?.get?.(meta.series);
          let value: number | undefined;

          if (typeof seriesValue === "number") {
            value = seriesValue;
          } else if (seriesValue && typeof seriesValue === "object" && "value" in seriesValue) {
            value = Number((seriesValue as { value: number }).value);
          }
          if (value == null) {
            value = meta.valueByDate.get(date);
          }
          if (value == null || Number.isNaN(value)) {
            return null;
          }
          return { name: meta.name, value, color: meta.color };
        })
        .filter((item): item is { name: string; value: number; color: string } => item !== null);

      if (rows.length === 0) {
        setTooltip(null);
        return;
      }

      setTooltip({ x, y, date, rows });
    };

    chartRef.current.subscribeCrosshairMove(handler);
    return () => {
      chartRef.current?.unsubscribeCrosshairMove(handler);
    };
  }, [lines]);

  if (lines.length === 0) {
    return (
      <div data-testid="multi-equity-chart-empty" className="rounded border border-slate-700 p-4 text-sm text-slate-400">
        尚無可比較的策略資金曲線。
      </div>
    );
  }

  return (
    <div data-testid="multi-equity-chart" className="space-y-2">
      <div className="relative" data-testid="multi-equity-chart-wrap">
        <div ref={containerRef} style={{ height }} />
        {tooltip && (
          <div
            data-testid="multi-equity-tooltip"
            className="pointer-events-none absolute z-10 min-w-[200px] rounded border border-slate-700 bg-slate-900/95 px-2 py-1 text-xs text-slate-200"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            <div className="mb-1 text-[11px] text-slate-400">{tooltip.date}</div>
            {tooltip.rows.map((row) => (
              <div key={row.name} className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-1">
                  <span style={{ backgroundColor: row.color }} className="inline-block h-2 w-2 rounded-full" />
                  <span>{row.name}</span>
                </span>
                <span>{row.value.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {lines.map((line) => (
          <div key={line.name} data-testid="multi-equity-legend-item" className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
            <span style={{ backgroundColor: line.color }} className="inline-block h-2 w-2 rounded-full" />
            <span>{line.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
