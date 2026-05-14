// Tests for DeleteConfirmDialog component (Phase 10-C-1)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeleteConfirmDialog } from "@/components/data/DeleteConfirmDialog";
import type { SymbolRow } from "@/types/data";

const TW_ROW: SymbolRow = {
  symbol: "2330",
  market: "tw",
  firstDate: "2010-01-04",
  lastDate: "2026-05-14",
  bars: 4012,
  status: "fresh",
  hasAdjusted: false,
};

const US_ROW: SymbolRow = {
  symbol: "AAPL",
  market: "us",
  firstDate: "2010-01-04",
  lastDate: "2026-05-13",
  bars: 4115,
  status: "fresh",
  hasAdjusted: true,
};

describe("DeleteConfirmDialog", () => {
  it("renders dialog when open=true", () => {
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByTestId("delete-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("delete-dialog-confirm")).toBeInTheDocument();
  });

  it("does not render dialog content when open=false", () => {
    render(
      <DeleteConfirmDialog
        open={false}
        row={null}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("delete-dialog")).not.toBeInTheDocument();
  });

  it("shows symbol code in dialog", () => {
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    // "2330" appears in both title and description — use getAllByText
    const codes = screen.getAllByText("2330");
    expect(codes.length).toBeGreaterThanOrEqual(1);
  });

  it("shows 台股 label for TW market", () => {
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/台股/)).toBeInTheDocument();
  });

  it("shows 美股 label for US market", () => {
    render(
      <DeleteConfirmDialog
        open={true}
        row={US_ROW}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/美股/)).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-dialog-confirm"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onClose when cancel button is clicked", () => {
    const onClose = vi.fn();
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={onClose}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-dialog-cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows 刪除中… and disables buttons when isDeleting=true", () => {
    render(
      <DeleteConfirmDialog
        open={true}
        row={TW_ROW}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isDeleting={true}
      />,
    );
    expect(screen.getByText("刪除中…")).toBeInTheDocument();
    expect(screen.getByTestId("delete-dialog-confirm")).toBeDisabled();
    expect(screen.getByTestId("delete-dialog-cancel")).toBeDisabled();
  });
});
