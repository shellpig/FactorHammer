"use client";

// Strategy preset dropdown — reads GET /api/config/strategies (Phase 10-E-1)

import useSWR from "swr";

interface StrategyPreset {
  name: string;
  type: string;
  params: Record<string, unknown>;
}

interface StrategyPresetSelectProps {
  value: number;
  onChange: (index: number) => void;
  disabled?: boolean;
}

const fetcher = (url: string) =>
  fetch(url).then((r) => r.json()).then((b) => b.data as StrategyPreset[]);

export function StrategyPresetSelect({
  value,
  onChange,
  disabled,
}: StrategyPresetSelectProps) {
  const { data: presets, isLoading } = useSWR<StrategyPreset[]>(
    "/api/config/strategies",
    fetcher,
  );

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-400">策略</label>
      <select
        data-testid="strategy-preset-select"
        className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled || isLoading || !presets}
      >
        {isLoading && <option value="">載入中…</option>}
        {presets?.map((p, i) => (
          <option key={i} value={i}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}
