// AI Chat page (Phase 10-F-1)

import type { Metadata } from "next";
import { ChatPageClient } from "@/components/ai/chat-page-client";

export const metadata: Metadata = {
  title: "AI 問答 | FactorHammer",
  description: "AI 股市問答助手。",
};

export default function AiPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-baseline gap-3 border-b border-border px-4 py-3">
        <h1 className="text-xl font-bold text-foreground">AI 問答</h1>
        <p className="text-xs text-muted-foreground">
          可提問範例：2330 的 RSI 是多少？回測 KD_Cross 在 2020 年的表現？
        </p>
        {/* Status chip */}
        <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-slate-600/40 bg-slate-700/30 px-2.5 py-0.5 text-xs font-medium text-slate-400">
          AI · 未啟用
        </span>
      </div>

      {/* Chat area */}
      <ChatPageClient />
    </div>
  );
}
