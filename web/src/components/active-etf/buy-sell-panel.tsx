import type { ActiveEtfHoldingsResponse } from "@/types/active-etf";
import { TrendingUp, TrendingDown } from "lucide-react";

interface BuySellPanelProps {
  data: ActiveEtfHoldingsResponse | null;
}

export function BuySellPanel({ data }: BuySellPanelProps) {
  const buysAndEntries = data?.changes
    ? [
        ...data.changes.buys.map((b) => ({ ...b, type: "buy" as const })),
        ...data.changes.entries.map((e) => ({ ...e, type: "entry" as const })),
      ].sort((a, b) => Math.abs(b.delta_shares) - Math.abs(a.delta_shares))
    : [];

  const sellsAndExits = data?.changes
    ? [
        ...data.changes.sells.map((s) => ({ ...s, type: "sell" as const })),
        ...data.changes.exits.map((e) => ({ ...e, type: "exit" as const })),
      ].sort((a, b) => Math.abs(b.delta_shares) - Math.abs(a.delta_shares))
    : [];

  return (
    <div className="rounded-lg border border-border bg-card text-card-foreground shadow-sm overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
        <div>
          <h2 className="font-semibold text-foreground" data-testid="changes-panel-title">
            持股變動
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5" data-testid="changes-panel-subtitle">
            {data?.has_previous
              ? `比較區間：${data.previous_date} → ${data.latest_date}`
              : "比較區間：首次擷取快照"}
          </p>
        </div>
      </div>

      <div className="p-4">
        {!data?.has_previous ? (
          <div className="py-6 text-center text-sm text-muted-foreground" data-testid="no-prev-data-msg">
            首次擷取，尚無前次資料可比較。
          </div>
        ) : buysAndEntries.length === 0 && sellsAndExits.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            本期持股無變化。
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Buy / Entry list */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-emerald-500 flex items-center gap-1.5 border-b border-border pb-1.5">
                <TrendingUp className="h-4 w-4" />
                買進 / 新進
              </h3>
              {buysAndEntries.length === 0 ? (
                <p className="text-xs text-muted-foreground py-2">無買進標的</p>
              ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {buysAndEntries.map((row) => (
                    <div
                      key={row.holding_code || row.holding_name}
                      className="flex items-center justify-between p-2 rounded-lg bg-muted/20 border border-border/30 hover:border-emerald-500/20 transition-all text-xs"
                      data-testid="buy-row"
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium text-foreground">{row.holding_name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {row.holding_code || "其他"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {row.type === "entry" && (
                          <span className="rounded bg-emerald-500/10 px-1 py-0.5 text-[10px] font-medium text-emerald-500">
                            新進
                          </span>
                        )}
                        <span className="font-mono font-semibold text-emerald-500">
                          +{row.delta_shares.toLocaleString()} 股
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Sell / Exit list */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-red-500 flex items-center gap-1.5 border-b border-border pb-1.5">
                <TrendingDown className="h-4 w-4" />
                賣出 / 剔除
              </h3>
              {sellsAndExits.length === 0 ? (
                <p className="text-xs text-muted-foreground py-2">無賣出標的</p>
              ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {sellsAndExits.map((row) => (
                    <div
                      key={row.holding_code || row.holding_name}
                      className="flex items-center justify-between p-2 rounded-lg bg-muted/20 border border-border/30 hover:border-red-500/20 transition-all text-xs"
                      data-testid="sell-row"
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium text-foreground">{row.holding_name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {row.holding_code || "其他"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {row.type === "exit" && (
                          <span className="rounded bg-red-500/10 px-1 py-0.5 text-[10px] font-medium text-red-500">
                            剔除
                          </span>
                        )}
                        <span className="font-mono font-semibold text-red-500">
                          {row.delta_shares.toLocaleString()} 股
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
