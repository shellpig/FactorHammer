"use client";

// Data management table with sticky header (Phase 10-C-1)
// 更新 button is disabled — 10-C-2 will enable it.

import { RefreshCw, Trash2 } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import type { SymbolRow } from "@/types/data";

interface DataTableProps {
  rows: SymbolRow[];
  onDelete: (row: SymbolRow) => void;
}

// col layout: code | name+variant | range | bars | status | actions
const GRID = "grid-cols-[100px_1fr_220px_80px_100px_180px]";

export function DataTable({ rows, onDelete }: DataTableProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 px-4 py-12 text-center text-sm text-slate-500">
        目前沒有本機資料。請先新增標的或下載歷史資料。
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 overflow-hidden">
      {/* Sticky header */}
      <div
        className={`sticky top-0 z-10 grid ${GRID} gap-3 border-b border-slate-800/70 bg-slate-900/95 px-4 py-2.5 text-[11px] uppercase tracking-wider text-slate-500 backdrop-blur`}
      >
        <div>代碼</div>
        <div>名稱</div>
        <div>區間</div>
        <div className="text-right">K 棒數</div>
        <div>狀態</div>
        <div className="pr-1 text-right">動作</div>
      </div>

      <div>
        {rows.map((row, i) => (
          <div
            key={row.symbol}
            data-testid={`data-row-${row.symbol}`}
            className={`grid ${GRID} gap-3 items-center px-4 py-3 text-sm transition-colors hover:bg-slate-800/40 ${
              i !== rows.length - 1 ? "border-b border-slate-800/70" : ""
            }`}
          >
            {/* 代碼 */}
            <div className="font-mono font-medium text-slate-100 truncate">
              {row.symbol}
            </div>

            {/* 名稱 (fallback to symbol; raw+adj badge for US) */}
            <div className="text-slate-100 truncate">
              {row.symbol}
              {row.market === "us" && (
                <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-500">
                  raw+adj
                </span>
              )}
            </div>

            {/* 區間 */}
            <div className="font-mono text-[12.5px] text-slate-300 truncate">
              {row.firstDate ?? "—"}
              <span className="text-slate-500"> ~ </span>
              {row.lastDate ?? "—"}
            </div>

            {/* K 棒數 */}
            <div className="font-mono text-right text-slate-300">
              {row.bars > 0 ? row.bars.toLocaleString() : "—"}
            </div>

            {/* 狀態 */}
            <div>
              <StatusBadge status={row.status} />
            </div>

            {/* 動作 */}
            <div className="flex items-center justify-end gap-1.5">
              {/* 更新 — disabled until 10-C-2 */}
              <button
                disabled
                title="Phase 10-C-2 開發中"
                className="inline-flex items-center gap-1 h-7 px-2.5 rounded-md text-xs border border-sky-500/30 bg-sky-500/10 text-sky-300 opacity-40 cursor-not-allowed"
              >
                <RefreshCw className="h-3 w-3" />
                更新
              </button>

              {/* 刪除 */}
              <button
                onClick={() => onDelete(row)}
                data-testid={`delete-btn-${row.symbol}`}
                className="inline-flex items-center gap-1 h-7 px-2.5 rounded-md text-xs border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"
              >
                <Trash2 className="h-3 w-3" />
                刪除
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
