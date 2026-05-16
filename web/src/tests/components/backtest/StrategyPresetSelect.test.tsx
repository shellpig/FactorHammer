// Tests for StrategyPresetSelect component (Phase 10-E-1)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StrategyPresetSelect } from "@/components/backtest/StrategyPresetSelect";

const MOCK_PRESETS = [
  { name: "MA20_MA60", type: "moving_average_cross", params: { short_window: 20, long_window: 60 } },
  { name: "RSI_14", type: "rsi", params: { period: 14 } },
  { name: "定期定額", type: "dollar_cost_averaging", params: {} },
];

// Mock SWR
const mockSwrReturn = {
  data: MOCK_PRESETS,
  isLoading: false,
};

vi.mock("swr", () => ({
  default: () => mockSwrReturn,
}));

describe("StrategyPresetSelect", () => {
  beforeEach(() => {
    mockSwrReturn.data = MOCK_PRESETS;
    mockSwrReturn.isLoading = false;
  });

  it("renders a select element", () => {
    render(<StrategyPresetSelect value={0} onChange={vi.fn()} />);
    expect(screen.getByTestId("strategy-preset-select")).toBeInTheDocument();
  });

  it("displays preset names from API", () => {
    render(<StrategyPresetSelect value={0} onChange={vi.fn()} />);
    expect(screen.getByText("MA20_MA60")).toBeInTheDocument();
    expect(screen.getByText("RSI_14")).toBeInTheDocument();
    expect(screen.getByText("定期定額")).toBeInTheDocument();
  });

  it("shows selected index value", () => {
    render(<StrategyPresetSelect value={1} onChange={vi.fn()} />);
    const select = screen.getByTestId("strategy-preset-select") as HTMLSelectElement;
    expect(select.value).toBe("1");
  });

  it("calls onChange with numeric index on selection", () => {
    const onChange = vi.fn();
    render(<StrategyPresetSelect value={0} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("strategy-preset-select"), {
      target: { value: "2" },
    });
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("disables when disabled=true", () => {
    render(<StrategyPresetSelect value={0} onChange={vi.fn()} disabled />);
    expect(screen.getByTestId("strategy-preset-select")).toBeDisabled();
  });

  it("disables when loading", () => {
    mockSwrReturn.isLoading = true;
    mockSwrReturn.data = undefined as unknown as typeof MOCK_PRESETS;
    render(<StrategyPresetSelect value={0} onChange={vi.fn()} />);
    expect(screen.getByTestId("strategy-preset-select")).toBeDisabled();
  });
});
