// Backtest job progress bar — shows phase + cancel button (Phase 10-E-1)

interface BacktestProgressBarProps {
  current?: number;
  total?: number;
  phase?: string;
  onCancel?: () => void;
  className?: string;
}

export function BacktestProgressBar({
  current,
  total,
  phase,
  onCancel,
  className,
}: BacktestProgressBarProps) {
  const pct =
    total && total > 0 && current != null
      ? Math.min((current / total) * 100, 100)
      : null;

  const phaseLabel: Record<string, string> = {
    loading_data: "載入資料中…",
    running: "回測執行中…",
  };
  const label = phase ? (phaseLabel[phase] ?? phase) : "回測執行中…";

  return (
    <div
      data-testid="backtest-progress-bar"
      className={`flex flex-col gap-1.5 ${className ?? ""}`}
    >
      <div className="flex items-center justify-between text-[12px] text-slate-400">
        <span>{label}</span>
        <div className="flex items-center gap-3">
          {pct != null && (
            <span data-testid="progress-count">
              {current} / {total}
            </span>
          )}
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded px-2 py-0.5 text-xs text-rose-400 hover:bg-rose-500/10 hover:text-rose-300"
            >
              取消
            </button>
          )}
        </div>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          data-testid="progress-fill"
          className="h-full rounded-full bg-sky-500 transition-all duration-300"
          style={{ width: pct != null ? `${pct}%` : "30%" }}
        />
      </div>
    </div>
  );
}
