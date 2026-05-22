"use client";

// Stock Selector component (Phase 10-B)
// TW: accepts symbol or name search (Enter to confirm)
// US: accepts ticker only (normalises BRK.B → BRK-B on the backend)

import { useEffect, useState } from "react";
import type { Market } from "@/types/market";
import { cn } from "@/lib/utils";
import { useCommandPaletteStockSource } from "@/hooks/use-command-palette";

interface StockSelectorProps {
  market: Market;
  value: string;
  onChange: (symbol: string) => void;
  onInputChange?: (value: string) => void;
  onSearch?: (query: string) => void;
  placeholder?: string;
  className?: string;
}

export function StockSelector({
  market,
  value,
  onChange,
  onInputChange,
  onSearch,
  placeholder,
  className,
}: StockSelectorProps) {
  const [inputValue, setInputValue] = useState(value);
  useCommandPaletteStockSource(market);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  const defaultPlaceholder =
    market === "tw"
      ? "股票代碼或名稱（Enter 送出）"
      : "美股代碼 (e.g. AAPL, BRK.B)";

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      const trimmed = inputValue.trim().toUpperCase();
      if (trimmed) {
        onChange(trimmed);
        onSearch?.(trimmed);
      }
    }
  }

  return (
    <input
      type="text"
      value={inputValue}
      onChange={(e) => {
        setInputValue(e.target.value);
        onInputChange?.(e.target.value);
      }}
      onKeyDown={handleKeyDown}
      placeholder={placeholder ?? defaultPlaceholder}
      className={cn(
        // Phase 14-B: temporary arbitrary value fix; remove after @theme token mapping is added.
        "w-full rounded-lg border border-border bg-[hsl(var(--background))] px-3 py-2",
        "text-sm text-foreground placeholder:text-muted-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring",
        className,
      )}
      aria-label={market === "tw" ? "台股代碼輸入" : "美股代碼輸入"}
      data-testid="stock-selector-input"
      autoComplete="off"
      spellCheck={false}
    />
  );
}
