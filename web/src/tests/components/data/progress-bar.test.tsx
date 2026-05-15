// Tests for ProgressBar component (Phase 10-C-2)

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProgressBar } from "@/components/data/ProgressBar";

describe("ProgressBar", () => {
  it("renders container, count, and fill testids", () => {
    render(<ProgressBar current={1} total={5} />);
    expect(screen.getByTestId("progress-bar")).toBeInTheDocument();
    expect(screen.getByTestId("progress-count")).toBeInTheDocument();
    expect(screen.getByTestId("progress-fill")).toBeInTheDocument();
  });

  it("shows current / total count", () => {
    render(<ProgressBar current={3} total={10} />);
    expect(screen.getByTestId("progress-count")).toHaveTextContent("3 / 10");
  });

  it("shows currentSymbol when provided", () => {
    render(<ProgressBar current={1} total={3} currentSymbol="2330" />);
    expect(screen.getByText("2330")).toBeInTheDocument();
  });

  it("shows 準備中… when no currentSymbol", () => {
    render(<ProgressBar current={0} total={3} />);
    expect(screen.getByText("準備中…")).toBeInTheDocument();
  });

  it("computes fill width as a percentage", () => {
    render(<ProgressBar current={2} total={4} />);
    const fill = screen.getByTestId("progress-fill");
    expect(fill).toHaveStyle({ width: "50%" });
  });

  it("clamps fill width to 100% when current exceeds total", () => {
    render(<ProgressBar current={10} total={5} />);
    const fill = screen.getByTestId("progress-fill");
    expect(fill).toHaveStyle({ width: "100%" });
  });

  it("renders 0% fill when total is 0", () => {
    render(<ProgressBar current={0} total={0} />);
    const fill = screen.getByTestId("progress-fill");
    expect(fill).toHaveStyle({ width: "0%" });
  });

  it("accepts additional className on container", () => {
    render(<ProgressBar current={1} total={2} className="my-custom" />);
    expect(screen.getByTestId("progress-bar")).toHaveClass("my-custom");
  });
});
