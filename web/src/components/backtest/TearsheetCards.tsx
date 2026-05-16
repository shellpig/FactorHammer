// Tearsheet: 5 metric cards for backtest results (Phase 10-E-1)

interface BacktestMetrics {
  total_trades: number | null;
  total_return: number | null;
  annual_return: number | null;
  max_drawdown: number | null;
  sharpe_ratio: number | null;
}

interface TearsheetCardsProps {
  metrics: BacktestMetrics;
  currency: "TWD" | "USD" | string;
  isDca?: boolean;
}

function MetricCard({
  label,
  value,
  sub,
  colorClass,
}: {
  label: string;
  value: string;
  sub?: string;
  colorClass?: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-800 p-3">
      <span className="text-[11px] text-slate-400">{label}</span>
      <span
        className={`text-lg font-semibold leading-tight ${colorClass ?? "text-slate-100"}`}
        data-testid="metric-value"
      >
        {value}
      </span>
      {sub && <span className="text-[10px] text-slate-500">{sub}</span>}
    </div>
  );
}

function pct(v: number | null, alwaysRed?: boolean): { text: string; cls: string } {
  if (v == null) return { text: "—", cls: "text-slate-400" };
  const formatted = `${(v * 100).toFixed(2)}%`;
  if (alwaysRed) return { text: formatted, cls: "text-rose-400" };
  return {
    text: formatted,
    cls: v >= 0 ? "text-emerald-400" : "text-rose-400",
  };
}

export function TearsheetCards({ metrics, currency, isDca = false }: TearsheetCardsProps) {
  const currencyLabel = `幣別：${currency}`;

  const totalReturn = pct(metrics.total_return);
  const annualReturn = pct(metrics.annual_return);
  const maxDrawdown = pct(metrics.max_drawdown, true);

  const sharpe =
    metrics.sharpe_ratio == null
      ? "—"
      : metrics.sharpe_ratio.toFixed(2);

  const tradesText = isDca || metrics.total_trades == null ? "定期定額不適用" : String(metrics.total_trades);
  const tradesCls = isDca || metrics.total_trades == null ? "text-slate-400" : "text-slate-100";

  return (
    <div
      data-testid="tearsheet-cards"
      className="grid grid-cols-5 gap-2"
    >
      <MetricCard
        label="交易次數"
        value={tradesText}
        sub={currencyLabel}
        colorClass={tradesCls}
      />
      <MetricCard
        label="總報酬率"
        value={totalReturn.text}
        sub={currencyLabel}
        colorClass={totalReturn.cls}
      />
      <MetricCard
        label="年化報酬率"
        value={annualReturn.text}
        sub={currencyLabel}
        colorClass={annualReturn.cls}
      />
      <MetricCard
        label="最大回撤"
        value={maxDrawdown.text}
        sub={currencyLabel}
        colorClass={maxDrawdown.cls}
      />
      <MetricCard
        label="Sharpe"
        value={sharpe}
        sub={currencyLabel}
        colorClass={
          metrics.sharpe_ratio == null
            ? "text-slate-400"
            : metrics.sharpe_ratio >= 1
              ? "text-emerald-400"
              : "text-slate-100"
        }
      />
    </div>
  );
}
