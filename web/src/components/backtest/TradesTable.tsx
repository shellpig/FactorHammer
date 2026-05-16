"use client";

// Trades table — sortable, paginated (Phase 10-E-1)

import { useState } from "react";

interface Trade {
  entry_date: string;
  exit_date: string;
  side: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  pnl: number;
  return_pct: number;
}

interface TradesTableProps {
  trades: Trade[];
  currency: string;
}

type SortKey = "entry_date" | "exit_date" | "pnl" | "return_pct" | "shares";

const PAGE_SIZE = 20;

function formatPrice(v: number, currency: string): string {
  if (currency === "USD") return `$${v.toFixed(2)}`;
  return v.toLocaleString("zh-TW");
}

function formatPnl(pnl: number, returnPct: number, currency: string): string {
  const sign = pnl >= 0 ? "+" : "";
  const pnlStr = currency === "USD" ? `$${pnl.toFixed(2)}` : pnl.toLocaleString("zh-TW");
  return `${sign}${pnlStr} (${(returnPct * 100).toFixed(2)}%)`;
}

export function TradesTable({ trades, currency }: TradesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("entry_date");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);

  if (trades.length === 0) {
    return (
      <div
        data-testid="trades-table-empty"
        className="rounded-lg border border-slate-700 p-4 text-center text-sm text-slate-400"
      >
        無交易記錄
      </div>
    );
  }

  const sorted = [...trades].sort((a, b) => {
    let cmp = 0;
    if (sortKey === "entry_date") cmp = a.entry_date.localeCompare(b.entry_date);
    else if (sortKey === "exit_date") cmp = a.exit_date.localeCompare(b.exit_date);
    else if (sortKey === "pnl") cmp = a.pnl - b.pnl;
    else if (sortKey === "return_pct") cmp = a.return_pct - b.return_pct;
    else if (sortKey === "shares") cmp = a.shares - b.shares;
    return sortAsc ? cmp : -cmp;
  });

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const visible = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortAsc((p) => !p);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
    setPage(0);
  }

  const thCls = "px-3 py-2 text-left text-[11px] text-slate-400 cursor-pointer select-none hover:text-slate-200";
  const tdCls = "px-3 py-2 text-sm";

  function SortIcon({ k }: { k: SortKey }) {
    if (k !== sortKey) return <span className="ml-1 opacity-30">↕</span>;
    return <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>;
  }

  return (
    <div data-testid="trades-table" className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full">
          <thead className="border-b border-slate-700 bg-slate-800/50">
            <tr>
              <th className={thCls} onClick={() => toggleSort("entry_date")}>
                進場日期<SortIcon k="entry_date" />
              </th>
              <th className={thCls} onClick={() => toggleSort("exit_date")}>
                出場日期<SortIcon k="exit_date" />
              </th>
              <th className={thCls}>方向</th>
              <th className={thCls}>進場價</th>
              <th className={thCls}>出場價</th>
              <th className={thCls} onClick={() => toggleSort("shares")}>
                數量（股）<SortIcon k="shares" />
              </th>
              <th className={thCls} onClick={() => toggleSort("pnl")}>
                損益<SortIcon k="pnl" />
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t, i) => {
              const pnlCls = t.pnl >= 0 ? "text-emerald-400" : "text-rose-400";
              return (
                <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/30">
                  <td className={tdCls}>{t.entry_date}</td>
                  <td className={tdCls}>{t.exit_date}</td>
                  <td className={`${tdCls} capitalize`}>{t.side}</td>
                  <td className={tdCls}>{formatPrice(t.entry_price, currency)}</td>
                  <td className={tdCls}>{formatPrice(t.exit_price, currency)}</td>
                  <td className={tdCls}>{t.shares.toLocaleString()}</td>
                  <td className={`${tdCls} ${pnlCls}`}>
                    {formatPnl(t.pnl, t.return_pct, currency)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>
            第 {page + 1} / {totalPages} 頁（共 {trades.length} 筆）
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded px-2 py-0.5 hover:bg-slate-700 disabled:opacity-40"
            >
              上一頁
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded px-2 py-0.5 hover:bg-slate-700 disabled:opacity-40"
            >
              下一頁
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
