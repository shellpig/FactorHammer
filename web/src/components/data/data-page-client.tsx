"use client";

// Data management page — full client implementation (Phase 10-C-1 + 10-C-2)
// 10-C-1: symbol list, status badges, DELETE with single-step dialog
// 10-C-2: 全部更新 / 全部重建 / 動作欄·更新 (all via Job+SSE) / + 新增標的

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Search, Plus, RefreshCw, Hammer, AlertTriangle } from "lucide-react";
import { MarketSwitcher } from "@/components/market-switcher";
import { DataTable } from "@/components/data/DataTable";
import { DeleteConfirmDialog } from "@/components/data/DeleteConfirmDialog";
import { AddSymbolDialog } from "@/components/data/AddSymbolDialog";
import { RebuildConfirmDialog } from "@/components/data/RebuildConfirmDialog";
import { ProgressBar } from "@/components/data/ProgressBar";
import { useDataList } from "@/lib/hooks/useDataList";
import { useDataJob } from "@/lib/hooks/useDataJob";
import { apiDelete } from "@/lib/api-client";
import type { SymbolRow } from "@/types/data";
import type { Market } from "@/types/market";
import { useToast } from "@/hooks/use-toast";

type DataJobIntent =
  | { type: "update_all" }
  | { type: "rebuild_all" }
  | { type: "add_symbol"; symbol: string }
  | { type: "update_symbol"; symbol: string };

export function DataPageClient() {
  const toast = useToast();
  const [market, setMarket] = useState<Market>("tw");
  const [search, setSearch] = useState("");

  // DELETE state
  const [deleteRow, setDeleteRow] = useState<SymbolRow | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Dialog toggles
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showRebuildDialog, setShowRebuildDialog] = useState(false);
  const [jobIntent, setJobIntent] = useState<DataJobIntent | null>(null);
  const notifyKeyRef = useRef<string | null>(null);

  const { rows, isLoading, error: listError, mutate } = useDataList(market);

  // Job hook — refresh list on completion
  const { status: jobStatus, current, total, currentSymbol, succeeded, failed,
    errorMsg: jobError, startJob, resetJob } = useDataJob(mutate);

  const isJobRunning = jobStatus === "running";

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((r) => r.symbol.toLowerCase().includes(q));
  }, [rows, search]);

  const stats = useMemo(
    () => ({
      total: rows.length,
      fresh: rows.filter((r) => r.status === "fresh").length,
      stale: rows.filter((r) => r.status === "stale").length,
      missing: rows.filter((r) => r.status === "missing").length,
    }),
    [rows],
  );

  // ── DELETE ────────────────────────────────────────────────────────────────

  async function handleDeleteConfirm() {
    if (!deleteRow) return;
    const target = deleteRow;
    setIsDeleting(true);
    try {
      await apiDelete(`/api/data/${target.market}/${target.symbol}`);
      toast.success(`已刪除：${target.symbol}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "刪除失敗，請稍後再試");
    } finally {
      setIsDeleting(false);
      setDeleteRow(null);
      mutate();
    }
  }

  function handleDeleteClose() {
    if (isDeleting) return;
    setDeleteRow(null);
  }

  // ── UPDATE (single symbol) ────────────────────────────────────────────────

  const handleUpdateSymbol = useCallback(
    async (row: SymbolRow) => {
      setJobIntent({ type: "update_symbol", symbol: row.symbol });
      await startJob("data_update", { market: row.market, symbols: [row.symbol] });
    },
    [startJob],
  );

  // ── BATCH UPDATE (全部更新) ────────────────────────────────────────────────

  async function handleUpdateAll() {
    setJobIntent({ type: "update_all" });
    await startJob("data_update", { market, all: true });
  }

  // ── REBUILD (全部重建) ─────────────────────────────────────────────────────

  async function handleRebuildConfirm() {
    setShowRebuildDialog(false);
    setJobIntent({ type: "rebuild_all" });
    await startJob("data_rebuild", { market, all: true });
  }

  // ── ADD SYMBOL (+ 新增標的) ────────────────────────────────────────────────

  async function handleAddSubmit(symbol: string) {
    setJobIntent({ type: "add_symbol", symbol });
    await startJob("data_update", { market, symbols: [symbol] });
  }

  // ── Job complete/error toast ──────────────────────────────────────────────

  useEffect(() => {
    if (jobStatus === "complete") {
      const failedSymbols = failed.map((item) => item.symbol);
      const completeKey = `complete:${jobIntent?.type ?? "none"}:${succeeded.join(",")}:${failedSymbols.join(",")}`;
      if (notifyKeyRef.current === completeKey) {
        return;
      }

      const matchSymbol = (value: string, target: string) =>
        value.trim().toUpperCase() === target.trim().toUpperCase();
      const getFailedReason = (target: string) =>
        failed.find((item) => matchSymbol(item.symbol, target))?.error;

      if (jobIntent?.type === "add_symbol") {
        const symbol = jobIntent.symbol.toUpperCase();
        const ok = succeeded.some((item) => matchSymbol(item, symbol));
        if (ok) {
          toast.success(`已新增標的：${symbol}`);
        } else {
          const reason = getFailedReason(symbol);
          toast.error(reason ? `新增失敗：${symbol}（${reason}）` : `新增失敗：${symbol}`);
        }
      } else if (jobIntent?.type === "update_symbol") {
        const symbol = jobIntent.symbol.toUpperCase();
        const ok = succeeded.some((item) => matchSymbol(item, symbol));
        if (ok) {
          toast.success(`已更新：${symbol}`);
        } else {
          const reason = getFailedReason(symbol);
          toast.error(reason ? `更新失敗：${symbol}（${reason}）` : `更新失敗：${symbol}`);
        }
      } else {
        const actionLabel = jobIntent?.type === "rebuild_all" ? "重建" : "更新";
        if (failed.length === 0) {
          toast.success(`${actionLabel}完成：${succeeded.length} 個成功`);
        } else {
          if (succeeded.length > 0) {
            toast.success(`${actionLabel}完成：${succeeded.length} 個成功`);
          }
          toast.error(
            `${actionLabel}失敗：${failed.length} 檔（${failedSymbols.join("、")}）`,
          );
        }
      }

      notifyKeyRef.current = completeKey;
      setJobIntent(null);
      resetJob();
      return;
    }

    if (jobStatus === "error" && jobError) {
      const errorKey = `error:${jobIntent?.type ?? "none"}:${jobError}`;
      if (notifyKeyRef.current !== errorKey) {
        toast.error(jobError);
        notifyKeyRef.current = errorKey;
      }
      setJobIntent(null);
      resetJob();
    }
  }, [failed, jobError, jobIntent, jobStatus, resetJob, succeeded, toast]);

  // ── Main render ───────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-4">
      {/* ── Header ── */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
            資料 / Data Management
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100">
            資料管理
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            管理本機歷史資料、更新與重建。資料儲存於{" "}
            <code className="font-mono text-[12px]">data/parquet</code> 與
            DuckDB metadata。
          </p>
        </div>
        <MarketSwitcher value={market} onChange={setMarket} />
      </div>

      {/* ── Toolbar ── */}
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between lg:gap-3">
        <div className="flex w-full min-w-0 items-center gap-2 lg:max-w-xl lg:flex-1">
          <label className="flex h-9 flex-1 items-center gap-2 rounded-md border border-slate-700/80 bg-slate-900/70 px-3 focus-within:border-slate-500">
            <Search className="h-4 w-4 shrink-0 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜尋代碼（例：2330、AAPL）"
              className="min-w-0 flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
            />
          </label>
          <button
            onClick={() => setShowAddDialog(true)}
            disabled={isJobRunning}
            className="inline-flex h-9 min-w-[7.25rem] shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md bg-slate-100 px-4 text-sm font-medium text-slate-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            新增標的
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2 lg:flex lg:items-center">
          <button
            onClick={() => mutate()}
            disabled={isJobRunning}
            className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700/80 bg-slate-900/40 px-2.5 text-[13px] text-slate-200 hover:bg-slate-800/60 disabled:cursor-not-allowed disabled:opacity-40 lg:h-9 lg:px-3 lg:text-sm"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            重新整理
          </button>
          <button
            onClick={handleUpdateAll}
            disabled={isJobRunning || rows.length === 0}
            className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700/80 bg-slate-900/40 px-2.5 text-[13px] text-slate-200 hover:bg-slate-800/60 disabled:cursor-not-allowed disabled:opacity-40 lg:h-9 lg:px-3 lg:text-sm"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            更新
          </button>
          <button
            onClick={() => setShowRebuildDialog(true)}
            disabled={isJobRunning || rows.length === 0}
            className="inline-flex h-10 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700/80 bg-slate-900/40 px-2.5 text-[13px] text-slate-200 hover:bg-slate-800/60 disabled:cursor-not-allowed disabled:opacity-40 lg:h-9 lg:px-3 lg:text-sm"
          >
            <Hammer className="h-3.5 w-3.5" />
            重建
          </button>
        </div>
      </div>

      {/* ── US market callout ── */}
      {market === "us" && (
        <div className="flex items-start gap-2.5 rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2 text-[12.5px] text-slate-400">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
          <span>
            美股模式僅支援日 K（資料來源：yfinance · America/New_York）。US-1
            範圍不含分 K 與籌碼資料；同一標的會同時保留{" "}
            <code className="font-mono text-[11.5px]">raw</code> 與{" "}
            <code className="font-mono text-[11.5px]">adjusted</code> 兩份。
          </span>
        </div>
      )}

      {/* ── Progress bar (visible while job running) ── */}
      {isJobRunning && (
        <div className="rounded-md border border-sky-500/20 bg-sky-500/5 px-4 py-3">
          <ProgressBar current={current} total={total} currentSymbol={currentSymbol} />
        </div>
      )}

      {/* ── List fetch error ── */}
      {listError && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          讀取失敗：{listError.message ?? "無法連線至後端 API"}
        </div>
      )}

      {/* ── Table / Loading ── */}
      {isLoading ? (
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 px-4 py-12 text-center text-sm text-slate-500">
          載入中…
        </div>
      ) : (
        <DataTable
          rows={filtered}
          onDelete={setDeleteRow}
          onUpdate={handleUpdateSymbol}
          isJobRunning={isJobRunning}
        />
      )}

      {/* ── Footer stats ── */}
      <div className="flex items-center justify-between text-[11.5px] text-slate-500">
        <span>
          資料來源：FinMind（台股）／ yfinance（美股）　·　本機快取存於{" "}
          <code className="font-mono text-[11px]">data/parquet</code> + DuckDB metadata
        </span>
        <span>
          共 <span className="text-slate-400">{stats.total}</span> 檔 ·{" "}
          {stats.fresh} 最新 · {stats.stale} 需更新 · {stats.missing} 缺資料
        </span>
      </div>

      {/* ── Dialogs ── */}
      <DeleteConfirmDialog
        open={deleteRow !== null}
        row={deleteRow}
        onClose={handleDeleteClose}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
      <AddSymbolDialog
        open={showAddDialog}
        market={market}
        onClose={() => setShowAddDialog(false)}
        onSubmit={handleAddSubmit}
      />
      <RebuildConfirmDialog
        open={showRebuildDialog}
        market={market}
        symbolCount={rows.length}
        onClose={() => setShowRebuildDialog(false)}
        onConfirm={handleRebuildConfirm}
        isRebuilding={isJobRunning}
      />
    </div>
  );
}
