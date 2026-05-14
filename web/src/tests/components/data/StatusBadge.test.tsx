// Tests for StatusBadge component (Phase 10-C-1)

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "@/components/data/StatusBadge";

describe("StatusBadge", () => {
  it("renders fresh badge with label 最新", () => {
    render(<StatusBadge status="fresh" />);
    const badge = screen.getByTestId("status-badge-fresh");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("最新");
  });

  it("renders stale badge with label 需更新", () => {
    render(<StatusBadge status="stale" />);
    const badge = screen.getByTestId("status-badge-stale");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("需更新");
  });

  it("renders missing badge with label 缺資料", () => {
    render(<StatusBadge status="missing" />);
    const badge = screen.getByTestId("status-badge-missing");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("缺資料");
  });

  it("accepts additional className", () => {
    const { container } = render(<StatusBadge status="fresh" className="my-custom" />);
    expect(container.firstChild).toHaveClass("my-custom");
  });
});
