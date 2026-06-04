import type { ActiveEtfHoldingsResponse } from "@/types/active-etf";

interface HoldingsTableProps {
  data: ActiveEtfHoldingsResponse | null;
}

export function HoldingsTable({ data }: HoldingsTableProps) {
  return (
    <div
      className="rounded-lg border border-border bg-card text-card-foreground shadow-sm overflow-hidden"
      data-testid="holdings-panel"
    >
      <div className="border-b border-border bg-muted/30 px-4 py-3">
        <h2 className="font-semibold text-foreground">目前總體持股</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-xs sm:text-sm border-collapse text-left" data-testid="holdings-table">
          <thead>
            <tr className="border-b border-border bg-muted/10 text-muted-foreground font-medium text-xs">
              <th className="p-2.5 w-14 text-center">排名</th>
              <th className="p-2.5 w-28">代碼</th>
              <th className="p-2.5">名稱</th>
              <th className="p-2.5 text-right">股數 (股)</th>
              <th className="p-2.5 text-right">權重 %</th>
              <th className="p-2.5 text-right w-36">Δ 股數 (較前次)</th>
            </tr>
          </thead>
          <tbody>
            {data?.holdings.map((row) => (
              <tr
                key={row.holding_code || row.holding_name}
                className="border-b border-border/50 hover:bg-muted/5 transition-colors"
                data-testid="holdings-table-row"
              >
                <td className="p-2.5 text-center text-muted-foreground font-mono">{row.rank}</td>
                <td className="p-2.5 font-mono font-medium text-foreground">
                  {row.holding_code || <span className="text-muted-foreground/40 font-sans">—</span>}
                </td>
                <td className="p-2.5 font-medium text-foreground">{row.holding_name}</td>
                <td className="p-2.5 text-right font-mono">{row.shares.toLocaleString()}</td>
                <td className="p-2.5 text-right font-mono">{row.weight_pct.toFixed(2)}%</td>
                <td className="p-2.5 text-right font-mono">
                  {!data.has_previous || row.delta_shares === null ? (
                    <span className="text-muted-foreground/30">—</span>
                  ) : row.delta_shares > 0 ? (
                    <span className="text-red-500 font-semibold">
                      +{row.delta_shares.toLocaleString()}
                    </span>
                  ) : row.delta_shares < 0 ? (
                    <span className="text-emerald-500 font-semibold">
                      {row.delta_shares.toLocaleString()}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
