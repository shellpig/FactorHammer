import type { ActiveEtf } from "@/types/active-etf";
import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface EtfSelectorProps {
  etfs: ActiveEtf[];
  selectedCode: string | null;
  onSelectEtf: (code: string) => void;
  isListLoading: boolean;
  isListError: boolean;
  isHoldingsLoading: boolean;
  onRefresh: () => void;
}

export function EtfSelector({
  etfs,
  selectedCode,
  onSelectEtf,
  isListLoading,
  isListError,
  isHoldingsLoading,
  onRefresh,
}: EtfSelectorProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2">
      <label htmlFor="etf-select" className="text-sm font-medium text-muted-foreground">
        主動式 ETF 標的：
      </label>
      <div className="flex items-center gap-2">
        <select
          id="etf-select"
          value={selectedCode || ""}
          onChange={(e) => onSelectEtf(e.target.value)}
          disabled={isListLoading}
          className={cn(
            "rounded-lg border border-border bg-[hsl(var(--background))] px-3 py-2 text-sm text-foreground",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
            "disabled:opacity-50 min-w-[200px]"
          )}
          data-testid="active-etf-selector"
        >
          {isListLoading ? (
            <option value="">載入名單中...</option>
          ) : isListError || etfs.length === 0 ? (
            <option value="">名單暫無，請確認 Token</option>
          ) : (
            <>
              <option value="">-- 請選擇 ETF --</option>
              {etfs.map((etf) => (
                <option key={etf.code} value={etf.code}>
                  {etf.code} {etf.name}
                </option>
              ))}
            </>
          )}
        </select>

        {selectedCode && (
          <button
            onClick={onRefresh}
            disabled={isHoldingsLoading}
            className={cn(
              "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground",
              "hover:bg-muted hover:text-foreground transition-colors focus:outline-none",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
            title="重新整理持股"
            data-testid="active-etf-refresh-btn"
          >
            <RefreshCw className={cn("h-4 w-4", isHoldingsLoading && "animate-spin")} />
          </button>
        )}
      </div>
    </div>
  );
}
