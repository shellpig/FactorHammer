"use client";

// Engine selector for backtest form (Phase 10-E-1)

import type { EngineType } from "@/types/backtest";

interface EngineSelectProps {
  value: EngineType;
  onChange: (v: EngineType) => void;
  disabled?: boolean;
}

const OPTIONS: { value: EngineType; label: string }[] = [
  { value: "vectorized", label: "向量化引擎" },
  { value: "event_driven", label: "事件驅動引擎" },
];

export function EngineSelect({ value, onChange, disabled }: EngineSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-400">引擎</label>
      <select
        data-testid="engine-select"
        className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 disabled:opacity-50"
        value={value}
        onChange={(e) => onChange(e.target.value as EngineType)}
        disabled={disabled}
      >
        {OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
