"use client";

// Date range picker for backtest form (Phase 10-E-1)
// Simple native date inputs — no external calendar library dependency

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onStartChange: (v: string) => void;
  onEndChange: (v: string) => void;
  disabled?: boolean;
}

export function DateRangePicker({
  startDate,
  endDate,
  onStartChange,
  onEndChange,
  disabled,
}: DateRangePickerProps) {
  return (
    <div className="flex items-end gap-2">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-400">起始日期</label>
        <input
          type="date"
          data-testid="start-date-input"
          value={startDate}
          max={endDate || undefined}
          onChange={(e) => onStartChange(e.target.value)}
          disabled={disabled}
          className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
        />
      </div>
      <span className="mb-1.5 text-slate-500">—</span>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-400">結束日期</label>
        <input
          type="date"
          data-testid="end-date-input"
          value={endDate}
          min={startDate || undefined}
          onChange={(e) => onEndChange(e.target.value)}
          disabled={disabled}
          className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
        />
      </div>
    </div>
  );
}
