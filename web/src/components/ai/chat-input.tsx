"use client";

import { useState, useRef } from "react";
import { SendHorizonal } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function submit() {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div
      className="flex items-center gap-2 border-t border-border bg-card px-3 py-3"
      data-testid="chat-input-bar"
    >
      <input
        ref={inputRef}
        type="text"
        placeholder="輸入你的問題..."
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(
          // Phase 14-B: temporary arbitrary value fix; remove after @theme token mapping is added.
          "flex-1 rounded-lg border border-border bg-[hsl(var(--background))] px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground",
          "outline-none focus:border-primary focus:ring-1 focus:ring-primary/30",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
        data-testid="chat-input-field"
        aria-label="訊息輸入框"
      />
      <button
        onClick={submit}
        disabled={disabled || !draft.trim()}
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors",
          "hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40",
        )}
        data-testid="chat-send-button"
        aria-label="送出"
      >
        <SendHorizonal className="h-4 w-4" />
      </button>
    </div>
  );
}
