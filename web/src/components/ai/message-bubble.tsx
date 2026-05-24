"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, ChevronUp, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import { ToolCall } from "@/hooks/use-ai-chat";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  error?: string;
  toolCalls?: ToolCall[];
}

export function MessageBubble({ role, content, error, toolCalls }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "flex flex-col gap-1",
        isUser ? "items-end" : "items-start",
      )}
      data-testid={`message-bubble-${role}`}
    >
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {isUser ? "你" : "AI"}
      </span>
      <div
        className={cn(
          "max-w-[78%] rounded-xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "border border-primary/30 bg-primary/10 text-foreground"
            : "border border-border bg-card text-foreground",
        )}
      >
        {content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => (
                <p className="mb-1 last:mb-0">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="mb-1 list-disc pl-4">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="mb-1 list-decimal pl-4">{children}</ol>
              ),
              li: ({ children }) => <li className="mb-0.5">{children}</li>,
              code: ({ children }) => (
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                  {children}
                </code>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold">{children}</strong>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        ) : error ? null : (
          <span
            className="inline-block animate-pulse text-muted-foreground"
            data-testid="chat-thinking-placeholder"
          >
            思考中...
          </span>
        )}

        {toolCalls && toolCalls.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-1 w-full" data-testid="tool-chips-container">
            {toolCalls.map((tc, idx) => (
              <ToolCallChip key={idx} {...tc} />
            ))}
          </div>
        )}

        {error && (
          <div className="mt-1 text-xs text-red-500 dark:text-red-400 font-medium" data-testid="chat-inline-error">
            ⚠️ 錯誤：{error}
          </div>
        )}
      </div>
    </div>
  );
}

export function ToolCallChip({ name, arguments: args, result }: ToolCall) {
  const [isOpen, setIsOpen] = useState(false);
  const isDone = !!result;
  const symbol = args?.symbol || "";
  const symbols = args?.symbols
    ? (Array.isArray(args.symbols) ? args.symbols.join(", ") : String(args.symbols))
    : symbol;

  const isPriceOnly = args?.dividend_policy === "price_only";

  // Compute status text dynamically based on current state and result
  let statusText = "";
  if (!isDone) {
    if (name === "get_price_data") {
      statusText = `正在更新與載入 ${symbols} 日線資料...`;
    } else if (name === "calculate_indicators") {
      statusText = `正在更新與載入 ${symbols} 日線資料並計算指標...`;
    } else if (name === "get_support_resistance") {
      statusText = `正在更新與載入 ${symbols} 日線資料並計算支撐壓力...`;
    } else if (name === "calculate_total_return") {
      statusText = `正在分析 ${symbols} 的${isPriceOnly ? "純股價" : "含息"}總報酬率...`;
    } else {
      statusText = `正在呼叫 ${name}...`;
    }
  } else {
    const summary = result?.output_summary || "";
    if (summary.includes("錯誤：")) {
      statusText = `執行失敗：${summary.replace("錯誤：", "")}`;
    } else if (summary.includes("更新失敗，改用本機既有資料")) {
      statusText = `⚠️ 更新失敗，使用 ${symbols} 本機既有資料`;
    } else if (summary.includes("資料更新正在進行中，暫用本機資料")) {
      statusText = `⚠️ 更新正在進行中，暫用 ${symbols} 本機資料`;
    } else if (summary.includes("資料更新正在進行中，稍後再試")) {
      statusText = `❌ 資料更新正在進行中，請稍後再試`;
    } else if (name === "calculate_total_return") {
      statusText = `已完成 ${symbols} 的${isPriceOnly ? "純股價" : "含息"}總報酬率計算`;
    } else {
      statusText = `已更新並分析 ${symbols} 日線資料`;
    }
  }

  const isWarning = statusText.includes("⚠️");
  const isError = statusText.includes("❌") || statusText.includes("執行失敗：");

  return (
    <div className={cn(
      "my-1.5 rounded-lg border p-2 text-xs w-full max-w-md select-none transition-all hover:bg-muted/50",
      isError
        ? "border-red-500/30 bg-red-500/5"
        : isWarning
          ? "border-amber-500/30 bg-amber-500/5"
          : "border-border bg-muted/40"
    )}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-medium min-w-0">
          <Cpu className={cn(
            "h-3.5 w-3.5 shrink-0",
            !isDone && "animate-spin text-primary",
            isError && "text-red-500",
            isWarning && "text-amber-500",
            isDone && !isError && !isWarning && "text-muted-foreground"
          )} />
          <span className={cn(
            "truncate",
            isError
              ? "text-red-500 dark:text-red-400"
              : isWarning
                ? "text-amber-500 dark:text-amber-400"
                : "text-muted-foreground"
          )}>
            {statusText}
          </span>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="rounded p-0.5 hover:bg-muted-foreground/10 text-muted-foreground shrink-0 cursor-pointer"
          data-testid="tool-chip-toggle"
        >
          {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {isOpen && (
        <div className="mt-2 border-t border-border/60 pt-1.5 font-mono text-[10px] text-muted-foreground space-y-1 overflow-x-auto whitespace-pre-wrap break-all" data-testid="tool-chip-details">
          <div>
            <span className="font-semibold">參數:</span> {JSON.stringify(args, null, 2)}
          </div>
          {result && (
            <div>
              <span className="font-semibold">結果:</span> {result.output_summary}
            </div>
          )}
        </div>
      )}

      {isDone && !isOpen && (
        <div className={cn(
          "mt-1 text-[11px] font-medium pl-5 truncate",
          isError
            ? "text-red-400/90"
            : isWarning
              ? "text-amber-400/90"
              : "text-primary/80"
        )} data-testid="tool-chip-summary">
          回傳：{result.output_summary}
        </div>
      )}
    </div>
  );
}
