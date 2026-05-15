// Tests for RebuildConfirmDialog component (Phase 10-C-2)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RebuildConfirmDialog } from "@/components/data/RebuildConfirmDialog";

describe("RebuildConfirmDialog", () => {
  it("renders dialog content when open=true", () => {
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={5}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rebuild-dialog")).toBeInTheDocument();
  });

  it("does not render dialog content when open=false", () => {
    render(
      <RebuildConfirmDialog
        open={false}
        market="tw"
        symbolCount={5}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("rebuild-dialog")).not.toBeInTheDocument();
  });

  it("shows 台股 label for tw market", () => {
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={3}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getAllByText(/台股/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows 美股 label for us market", () => {
    render(
      <RebuildConfirmDialog
        open={true}
        market="us"
        symbolCount={3}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getAllByText(/美股/).length).toBeGreaterThanOrEqual(1);
  });

  it("displays the symbol count in the description", () => {
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={42}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={5}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId("rebuild-dialog-confirm"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onClose when cancel button is clicked", () => {
    const onClose = vi.fn();
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={5}
        onClose={onClose}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("rebuild-dialog-cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows 重建中… and disables buttons when isRebuilding=true", () => {
    render(
      <RebuildConfirmDialog
        open={true}
        market="tw"
        symbolCount={5}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isRebuilding={true}
      />,
    );
    expect(screen.getByText("重建中…")).toBeInTheDocument();
    expect(screen.getByTestId("rebuild-dialog-confirm")).toBeDisabled();
    expect(screen.getByTestId("rebuild-dialog-cancel")).toBeDisabled();
    expect(screen.getByTestId("rebuild-dialog-close")).toBeDisabled();
  });
});
