// Tests for DateRangePicker component (Phase 10-E-1)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DateRangePicker } from "@/components/backtest/DateRangePicker";

describe("DateRangePicker", () => {
  it("renders start and end date inputs", () => {
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={vi.fn()}
        onEndChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("start-date-input")).toBeInTheDocument();
    expect(screen.getByTestId("end-date-input")).toBeInTheDocument();
  });

  it("shows default start date value", () => {
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={vi.fn()}
        onEndChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("start-date-input")).toHaveValue("2020-01-01");
  });

  it("shows default end date value", () => {
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={vi.fn()}
        onEndChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("end-date-input")).toHaveValue("2024-12-31");
  });

  it("calls onStartChange when start date changes", () => {
    const onStart = vi.fn();
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={onStart}
        onEndChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("start-date-input"), {
      target: { value: "2021-06-01" },
    });
    expect(onStart).toHaveBeenCalledWith("2021-06-01");
  });

  it("calls onEndChange when end date changes", () => {
    const onEnd = vi.fn();
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={vi.fn()}
        onEndChange={onEnd}
      />,
    );
    fireEvent.change(screen.getByTestId("end-date-input"), {
      target: { value: "2023-12-31" },
    });
    expect(onEnd).toHaveBeenCalledWith("2023-12-31");
  });

  it("disables both inputs when disabled=true", () => {
    render(
      <DateRangePicker
        startDate="2020-01-01"
        endDate="2024-12-31"
        onStartChange={vi.fn()}
        onEndChange={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByTestId("start-date-input")).toBeDisabled();
    expect(screen.getByTestId("end-date-input")).toBeDisabled();
  });
});
