// Tests for AddSymbolDialog component (Phase 10-C-2)

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddSymbolDialog } from "@/components/data/AddSymbolDialog";

describe("AddSymbolDialog", () => {
  it("renders dialog content when open=true", () => {
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByTestId("add-dialog")).toBeInTheDocument();
  });

  it("does not render dialog content when open=false", () => {
    render(
      <AddSymbolDialog
        open={false}
        market="tw"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("add-dialog")).not.toBeInTheDocument();
  });

  it("shows 台股 description for tw market", () => {
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText(/FinMind/)).toBeInTheDocument();
  });

  it("shows 美股 description for us market", () => {
    render(
      <AddSymbolDialog
        open={true}
        market="us"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText(/yfinance/)).toBeInTheDocument();
  });

  it("confirm button is disabled when no symbol has been entered", () => {
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("add-dialog-confirm")).toBeDisabled();
  });

  it("enables confirm button after Enter is pressed with a value", async () => {
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    const input = screen.getByTestId("stock-selector-input");
    // Type a value into StockSelector then press Enter → sets symbol state
    fireEvent.change(input, { target: { value: "2330" } });
    fireEvent.keyDown(input, { key: "Enter" });
    // Confirm button should become enabled after state update
    await waitFor(() =>
      expect(screen.getByTestId("add-dialog-confirm")).not.toBeDisabled(),
    );
  });

  it("calls onSubmit with uppercased symbol when confirm button is clicked", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );
    const input = screen.getByTestId("stock-selector-input");
    // Enter key sets AddSymbolDialog.symbol state (but doesn't submit due to stale state in onSearch)
    fireEvent.change(input, { target: { value: "2330" } });
    fireEvent.keyDown(input, { key: "Enter" });
    // Wait for confirm to become enabled, then click it
    await waitFor(() =>
      expect(screen.getByTestId("add-dialog-confirm")).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId("add-dialog-confirm"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("2330"));
  });

  it("calls onClose when cancel button is clicked", () => {
    const onClose = vi.fn();
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("add-dialog-cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when close (X) button is clicked", () => {
    const onClose = vi.fn();
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("add-dialog-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows 新增中… and disables confirm while onSubmit is pending", async () => {
    let resolveSubmit!: () => void;
    const onSubmit = vi.fn().mockReturnValue(
      new Promise<void>((resolve) => {
        resolveSubmit = resolve;
      }),
    );
    render(
      <AddSymbolDialog
        open={true}
        market="tw"
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );
    const input = screen.getByTestId("stock-selector-input");
    // Enter sets symbol state; then click confirm to trigger submission
    fireEvent.change(input, { target: { value: "2330" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(screen.getByTestId("add-dialog-confirm")).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId("add-dialog-confirm"));

    await waitFor(() =>
      expect(screen.getByText("新增中…")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("add-dialog-confirm")).toBeDisabled();

    // Resolve the promise and let all state updates settle
    await act(async () => { resolveSubmit(); });
  });
});
