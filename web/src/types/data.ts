// Phase 10-C types — data management page

export type DataStatus = "fresh" | "stale" | "missing";
export type DataType = "raw_daily" | "adjusted_daily";

export interface SymbolStatusRaw {
  symbol: string;
  market: string;
  data_type: DataType;
  available: boolean;
  row_count: number;
  start_date: string; // "YYYY-MM-DD" or "-"
  end_date: string;   // "YYYY-MM-DD" or "-"
}

export interface SymbolStatusResponse {
  data: SymbolStatusRaw[];
  meta: { market: string; symbol: string };
}

export interface SymbolsListResponse {
  data: Array<{ symbol: string; market: string; [key: string]: unknown }>;
  meta: { market: string; count: number };
}

export interface SymbolRow {
  symbol: string;
  market: "tw" | "us";
  firstDate: string | null;
  lastDate: string | null;
  bars: number;
  status: DataStatus;
  hasAdjusted: boolean;
}

export const STATUS_LABEL: Record<DataStatus, string> = {
  fresh:   "最新",
  stale:   "需更新",
  missing: "缺資料",
};
