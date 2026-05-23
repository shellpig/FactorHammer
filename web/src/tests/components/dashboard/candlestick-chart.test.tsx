import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OhlcvBar } from "@/types/analysis";
import { CandlestickChart } from "@/components/dashboard/candlestick-chart";

const mockSetVisibleLogicalRange = vi.fn();

const mockCandleSeries = {
  setData: vi.fn(),
  createPriceLine: vi.fn(() => ({ remove: vi.fn() })),
  removePriceLine: vi.fn(),
};

const mockVolumeSeries = {
  setData: vi.fn(),
  priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
};

const mockLineSeries = {
  setData: vi.fn(),
};

const mockChart = {
  addSeries: vi.fn((SeriesClass: unknown) => {
    if (SeriesClass === "CandlestickSeries") return mockCandleSeries;
    if (SeriesClass === "HistogramSeries") return mockVolumeSeries;
    return mockLineSeries;
  }),
  priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
  timeScale: vi.fn(() => ({ setVisibleLogicalRange: mockSetVisibleLogicalRange })),
  subscribeCrosshairMove: vi.fn(),
  remove: vi.fn(),
};

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: "CandlestickSeries",
  HistogramSeries: "HistogramSeries",
  LineSeries: "LineSeries",
  LineStyle: { Dashed: 2 },
  ColorType: { Solid: "Solid" },
  createChart: vi.fn(() => mockChart),
}));

function buildDailyBars(count: number, startIsoDate: string, stepDays: number): OhlcvBar[] {
  const start = new Date(startIsoDate).getTime();
  return Array.from({ length: count }, (_, idx) => {
    const ts = start + idx * stepDays * 24 * 60 * 60 * 1000;
    return {
      date: new Date(ts).toISOString(),
      open: 100 + idx,
      high: 101 + idx,
      low: 99 + idx,
      close: 100.5 + idx,
      volume: 1000 + idx,
      symbol: "2330",
    };
  });
}

function buildMinuteBars(count: number, startIsoDateTime: string, stepMinutes: number): OhlcvBar[] {
  const start = new Date(startIsoDateTime).getTime();
  return Array.from({ length: count }, (_, idx) => {
    const ts = start + idx * stepMinutes * 60 * 1000;
    return {
      date: new Date(ts).toISOString(),
      open: 100 + idx,
      high: 101 + idx,
      low: 99 + idx,
      close: 100.5 + idx,
      volume: 1000 + idx,
      symbol: "2330",
    };
  });
}

describe("CandlestickChart default right padding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("applies day interval right padding (+7 bars)", () => {
    const daily = buildDailyBars(10, "2026-01-01T00:00:00Z", 1);
    render(
      <CandlestickChart
        market="tw"
        interval="day"
        daily={daily}
        intraday={[]}
      />,
    );

    expect(mockSetVisibleLogicalRange).toHaveBeenLastCalledWith({
      from: 0,
      to: 16,
    });
  });

  it("applies week interval right padding (+2 bars)", () => {
    const daily = buildDailyBars(10, "2026-01-05T00:00:00Z", 7);
    render(
      <CandlestickChart
        market="tw"
        interval="week"
        daily={daily}
        intraday={[]}
      />,
    );

    expect(mockSetVisibleLogicalRange).toHaveBeenLastCalledWith({
      from: 0,
      to: 11,
    });
  });

  it("applies month interval right padding (+1 bar)", () => {
    const daily = buildDailyBars(10, "2026-01-01T00:00:00Z", 35);
    render(
      <CandlestickChart
        market="tw"
        interval="month"
        daily={daily}
        intraday={[]}
      />,
    );

    expect(mockSetVisibleLogicalRange).toHaveBeenLastCalledWith({
      from: 0,
      to: 10,
    });
  });

  it("applies minute interval right padding (+7 bars)", () => {
    const daily = buildDailyBars(5, "2026-01-01T00:00:00Z", 1);
    const intraday = buildMinuteBars(10, "2026-01-01T09:00:00Z", 1);
    render(
      <CandlestickChart
        market="tw"
        interval="minute"
        daily={daily}
        intraday={intraday}
      />,
    );

    expect(mockSetVisibleLogicalRange).toHaveBeenLastCalledWith({
      from: 0,
      to: 16,
    });
  });
});
