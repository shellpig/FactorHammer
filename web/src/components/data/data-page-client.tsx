"use client";

// Data management page — full client implementation (Phase 10-C-1)
// Implements: symbol list, status badges, delete with confirmation dialog.
// Stage-2 buttons (全部更新 / 全部重建 / 更新 / + 新增) are disabled until 10-C-2.

import { useState, useMemo } from "react";
import { Search, Plus, RefreshCw, Hammer, AlertTriangle } from "lucide-react";
import { MarketSwitcher } from "@/components/market-switcher";
import { DataTable } from "@/components/data/DataTable";
import { DeleteConfirmDialog } from "@/components/data/DeleteConfirmDialog";
import { useDataList } from "@/lib/hooks/useDataList";
import { apiDelete } from "@/lib/api-client";
import type { SymbolRow } from "@/types/data";
import type { Market } from "@/types/market";

export function DataPageClient() {
  const [market, setMarket] = useState<Market>("tw");
  const [search, setSearch] = useState("");
  const [deleteRow, setDeleteRow] = useState<SymbolRow | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { rows, isLoading, error, mutate } = useDataList(market);

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

  async function handleDeleteConfirm() {
    if (!deleteRow) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await apiDelete(`/api/data/${deleteRow.market}/${deleteRow.symbol}`);
      setDeleteRow(null);
      mutate();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "刪除失敗，請稍後再試");
    } finally {
      setIsDeleting(false);
    }
  }

  function handleDeleteClose() {
    if (isDeleting) return;
    setDeleteRow(null);
    setDeleteError(null);
  }

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
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-1 max-w-xl items-center gap-2">
          <label className="flex h-9 flex-1 items-center gap-2 rounded-md border border-slate-700/80 bg-slate-900/70 px-3 focus-within:border-slate-500">
            <Search className="h-4 w-4 shrink-0 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜尋代碼（例：2330、AAPL）"
              className="flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
            />
          </label>
          {/* + 新增標的 — disabled until 10-C-2 */}
          <button
            disabled
            title="Phase 10-C-2 開發中"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-slate-100 px-3 text-sm font-medium text-slate-900 opacity-40 cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            新增標的
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => mutate()}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-700/80 bg-slate-900/40 px-3 text-sm text-slate-200 hover:bg-slate-800/60"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            重新整理列表
          </button>
          {/* 全部更新 — disabled until 10-C-2 */}
          <button
            disabled
            title="Phase 10-C-2 開發中"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-700/80 bg-slate-900/40 px-3 text-sm text-slate-200 opacity-40 cursor-not-allowed"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            全部更新
          </button>
          {/* 全部重建 — disabled until 10-C-2 */}
          <button
            disabled
            title="Phase 10-C-2 開發中"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-700/80 bg-slate-900/40 px-3 text-sm text-slate-200 opacity-40 cursor-not-allowed"
          >
            <Hammer className="h-3.5 w-3.5" />
            全部重建
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

      {/* ── Error banners ── */}
      {error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          讀取失敗：{error.message ?? "無法連線至後端 API"}
        </div>
      )}
      {deleteError && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          刪除失敗：{deleteError}
        </div>
      )}

      {/* ── Table / Loading ── */}
      {isLoading ? (
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 px-4 py-12 text-center text-sm text-slate-500">
          載入中…
        </div>
      ) : (
        <DataTable rows={filtered} onDelete={setDeleteRow} />
      )}

      {/* ── Footer stats ── */}
      <div className="flex items-center justify-between text-[11.5px] text-slate-500">
        <span>
          資料來源：FinMind（台股）／ yfinance（美股）　·　本機快取存於{" "}
          <code className="font-mono text-[11px]">data/parquet</code> + DuckDB
          metadata
        </span>
        <span>
          共 <span className="text-slate-400">{stats.total}</span> 檔 ·{" "}
          {stats.fresh} 最新 · {stats.stale} 需更新 · {stats.missing} 缺資料
        </span>
      </div>

      {/* ── Delete dialog ── */}
      <DeleteConfirmDialog
        open={deleteRow !== null}
        row={deleteRow}
        onClose={handleDeleteClose}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </div>
  );
}
