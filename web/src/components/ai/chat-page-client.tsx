"use client";

import { useState, useEffect, useRef } from "react";
import { DisclaimerGate, isDisclaimerAccepted } from "./disclaimer-gate";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { useAIChat } from "@/hooks/use-ai-chat";

export function ChatPageClient() {
  const [accepted, setAccepted] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { messages, streaming, send, abort } = useAIChat();

  // Read localStorage after mount (avoid SSR mismatch)
  useEffect(() => {
    setAccepted(isDisclaimerAccepted());
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // While checking localStorage, render nothing to avoid flash
  if (accepted === null) return null;

  if (!accepted) {
    return (
      <div className="flex h-full flex-col" data-testid="chat-page">
        <DisclaimerGate onAccept={() => setAccepted(true)} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" data-testid="chat-page">
      {/* Message list */}
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            role={msg.role}
            content={msg.content}
            error={msg.error}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="relative">
        <ChatInput onSend={send} disabled={streaming} />
        {streaming && (
          <button
            onClick={abort}
            className="absolute right-16 top-1/2 -translate-y-1/2 rounded-lg bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 active:scale-95 transition-all shadow-sm"
            data-testid="chat-cancel-button"
          >
            取消
          </button>
        )}
      </div>
    </div>
  );
}
