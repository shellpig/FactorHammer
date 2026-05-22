import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DataPageClient } from "@/components/data/data-page-client";
import type { SymbolRow } from "@/types/data";

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
const mockToastInfo = vi.fn();
const mockToastDismiss = vi.fn();
const mockMutate = vi.fn();
const mockStartJob = vi.fn(async () => undefined);
const mockResetJob = vi.fn();
const mockApiDelete = vi.fn(async (_path: string) => ({ data: {}, meta: {} }));

let mockRows: SymbolRow[] = [];
let mockJobState = {
  status: "idle" as "idle" | "running" | "complete" | "error",
  current: 0,
  total: 0,
  currentSymbol: "",
  succeeded: [] as string[],
  failed: [] as Array<{ symbol: string; error: string }>,
  errorMsg: null as string | null,
};

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
    info: mockToastInfo,
    dismiss: mockToastDismiss,
  }),
}));

vi.mock("@/lib/hooks/useDataList", () => ({
  useDataList: () => ({
    rows: mockRows,
    isLoading: false,
    error: undefined,
    mutate: mockMutate,
  }),
}));

vi.mock("@/lib/hooks/useDataJob", () => ({
  useDataJob: () => ({
    ...mockJobState,
    startJob: mockStartJob,
    resetJob: mockResetJob,
  }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return {
    ...actual,
    apiDelete: (path: string) => mockApiDelete(path),
  };
});

vi.mock("@/components/market-switcher", () => ({
  MarketSwitcher: ({ value }: { value: string }) => <div data-testid="market-switcher">{value}</div>,
}));

vi.mock("@/components/data/ProgressBar", () => ({
  ProgressBar: () => <div data-testid="progress-bar" />,
}));

vi.mock("@/components/data/DataTable", () => ({
  DataTable: ({
    rows,
    onDelete,
    onUpdate,
  }: {
    rows: SymbolRow[];
    onDelete: (row: SymbolRow) => void;
    onUpdate: (row: SymbolRow) => void;
  }) => (
    <div data-testid="data-table">
      {rows.map((row) => (
        <div key={row.symbol} data-testid={`row-${row.symbol}`}>
          <button type="button" onClick={() => onUpdate(row)}>
            update-{row.symbol}
          </button>
          <button type="button" onClick={() => onDelete(row)}>
            delete-{row.symbol}
          </button>
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/data/DeleteConfirmDialog", () => ({
  DeleteConfirmDialog: ({
    open,
    onConfirm,
  }: {
    open: boolean;
    onConfirm: () => Promise<void>;
  }) =>
    open ? (
      <button type="button" onClick={() => void onConfirm()}>
        confirm-delete
      </button>
    ) : null,
}));

vi.mock("@/components/data/AddSymbolDialog", () => ({
  AddSymbolDialog: ({
    open,
    onSubmit,
  }: {
    open: boolean;
    onSubmit: (symbol: string) => Promise<void>;
  }) =>
    open ? (
      <button type="button" onClick={() => void onSubmit("2330")}>
        confirm-add
      </button>
    ) : null,
}));

vi.mock("@/components/data/RebuildConfirmDialog", () => ({
  RebuildConfirmDialog: ({
    open,
    onConfirm,
  }: {
    open: boolean;
    onConfirm: () => Promise<void>;
  }) =>
    open ? (
      <button type="button" onClick={() => void onConfirm()}>
        confirm-rebuild
      </button>
    ) : null,
}));

describe("DataPageClient toast migration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRows = [
      {
        symbol: "2330",
        market: "tw",
        name: "台積電",
        firstDate: "2024-01-01",
        lastDate: "2026-05-15",
        bars: 300,
        status: "fresh",
        hasAdjusted: true,
      },
    ];
    mockJobState = {
      status: "idle",
      current: 0,
      total: 0,
      currentSymbol: "",
      succeeded: [],
      failed: [],
      errorMsg: null,
    };
  });

  it("keeps mobile toolbar buttons on two rows without wrapping labels", () => {
    render(<DataPageClient />);

    const addButton = screen.getByRole("button", { name: "新增標的" });
    expect(addButton).toHaveClass("min-w-[7.25rem]");
    expect(addButton).toHaveClass("whitespace-nowrap");

    const refreshButton = screen.getByRole("button", { name: "重新整理" });
    const updateButton = screen.getByRole("button", { name: "更新" });
    const rebuildButton = screen.getByRole("button", { name: "重建" });
    expect(refreshButton.parentElement).toHaveClass("grid", "grid-cols-3", "lg:flex");
    for (const button of [refreshButton, updateButton, rebuildButton]) {
      expect(button).toHaveClass("h-10", "whitespace-nowrap", "lg:h-9");
    }
  });

  it("shows toast for update all completion and no inline result banner", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "更新" }));
    expect(mockStartJob).toHaveBeenCalledWith("data_update", { market: "tw", all: true });

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: ["2330"],
      failed: [],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("更新完成：1 個成功");
      expect(mockResetJob).toHaveBeenCalled();
    });
    expect(screen.queryByText("完成：1 個成功")).not.toBeInTheDocument();
  });

  it("shows failure toast list when rebuild all has failed symbols", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "重建" }));
    await userEvent.click(screen.getByRole("button", { name: "confirm-rebuild" }));
    expect(mockStartJob).toHaveBeenCalledWith("data_rebuild", { market: "tw", all: true });

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: ["2330"],
      failed: [{ symbol: "0050", error: "boom" }],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("重建失敗：1 檔（0050）");
    });
  });

  it("shows add symbol success toast", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "新增標的" }));
    await userEvent.click(screen.getByRole("button", { name: "confirm-add" }));

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: ["2330"],
      failed: [],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("已新增標的：2330");
    });
  });

  it("shows single update success toast", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "update-2330" }));
    expect(mockStartJob).toHaveBeenCalledWith("data_update", {
      market: "tw",
      symbols: ["2330"],
    });

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: ["2330"],
      failed: [],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("已更新：2330");
    });
  });

  it("shows single update failure toast when symbol is in failed list", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "update-2330" }));

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: [],
      failed: [{ symbol: "2330", error: "來源暫時不可用" }],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("更新失敗：2330（來源暫時不可用）");
      expect(mockToastSuccess).not.toHaveBeenCalledWith("已更新：2330");
    });
  });

  it("shows add symbol failure toast when symbol is not succeeded", async () => {
    const view = render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "新增標的" }));
    await userEvent.click(screen.getByRole("button", { name: "confirm-add" }));

    mockJobState = {
      ...mockJobState,
      status: "complete",
      succeeded: [],
      failed: [{ symbol: "2330", error: "無效代碼" }],
    };
    view.rerender(<DataPageClient />);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("新增失敗：2330（無效代碼）");
      expect(mockToastSuccess).not.toHaveBeenCalledWith("已新增標的：2330");
    });
  });

  it("shows delete success toast", async () => {
    render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "delete-2330" }));
    await userEvent.click(screen.getByRole("button", { name: "confirm-delete" }));

    await waitFor(() => {
      expect(mockApiDelete).toHaveBeenCalledWith("/api/data/tw/2330");
      expect(mockToastSuccess).toHaveBeenCalledWith("已刪除：2330");
    });
  });

  it("on delete failure: closes dialog, refreshes list, shows error toast", async () => {
    mockApiDelete.mockRejectedValueOnce(new Error("刪除部分失敗：parquet: [WinError 5]（檔案可能正被後端使用）"));
    render(<DataPageClient />);
    await userEvent.click(screen.getByRole("button", { name: "delete-2330" }));
    await userEvent.click(screen.getByRole("button", { name: "confirm-delete" }));

    await waitFor(() => {
      // Dialog must be closed (confirm-delete button gone)
      expect(screen.queryByRole("button", { name: "confirm-delete" })).not.toBeInTheDocument();
      // List must be refreshed
      expect(mockMutate).toHaveBeenCalled();
      // Error toast shown
      expect(mockToastError).toHaveBeenCalledWith(expect.stringContaining("WinError 5"));
    });
  });
});
