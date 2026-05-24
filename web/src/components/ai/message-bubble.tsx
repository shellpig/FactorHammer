"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  error?: string;
}

export function MessageBubble({ role, content, error }: MessageBubbleProps) {
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

        {error && (
          <div className="mt-1 text-xs text-red-500 dark:text-red-400 font-medium" data-testid="chat-inline-error">
            ⚠️ 錯誤：{error}
          </div>
        )}
      </div>
    </div>
  );
}
