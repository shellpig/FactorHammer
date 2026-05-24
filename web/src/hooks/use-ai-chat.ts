import { useState, useRef } from "react";

export interface Message {
  role: "user" | "assistant";
  content: string;
  error?: string;
  isGreeting?: boolean;
}

const GREETING_CONTENT =
  "你好。可提問範例：2330 的 RSI 是多少？／回測 KD_Cross 在 2020 年的表現？";

const GREETING: Message = {
  role: "assistant",
  content: GREETING_CONTENT,
  isGreeting: true,
};

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function nextFrame() {
  return new Promise<void>((resolve) => {
    if (typeof requestAnimationFrame !== "undefined") {
      requestAnimationFrame(() => resolve());
    } else {
      setTimeout(resolve, 0);
    }
  });
}

export function toApiMessages(messages: Message[]) {
  return messages
    .filter((msg) => {
      if (msg.role !== "user" && msg.role !== "assistant") return false;
      if (msg.isGreeting === true) return false;
      if (msg.role === "assistant" && msg.content === GREETING_CONTENT) return false;
      if (!msg.content.trim()) return false;
      return true;
    })
    .map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));
}

export function useAIChat() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [streaming, setStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  function abort() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreaming(false);
  }

  async function send(userText: string) {
    const trimmed = userText.trim();
    if (!trimmed || streaming) return;

    // Build the updated messages list
    const newUserMessage: Message = { role: "user", content: trimmed };
    const newAssistantMessage: Message = { role: "assistant", content: "" };

    const updatedMessages = [...messages, newUserMessage];
    setMessages([...updatedMessages, newAssistantMessage]);
    setStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${BASE_URL}/api/ai/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: toApiMessages(updatedMessages),
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const errorDetail = body?.detail?.error?.message || body?.detail || `HTTP ${response.status}`;
        throw new Error(errorDetail);
      }

      if (!response.body) {
        throw new Error("伺服器未回傳資料流。");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE standard line split (supporting both LF and CRLF)
        const normalized = buffer.replace(/\r\n/g, "\n");
        const parts = normalized.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          if (!part.trim()) continue;

          let eventType = "message";
          let eventData = "";

          const lines = part.split("\n");
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.substring(6).trim();
            } else if (line.startsWith("data:")) {
              let dataVal = line.substring(5);
              if (dataVal.startsWith(" ")) {
                dataVal = dataVal.substring(1);
              }
              eventData += (eventData ? "\n" : "") + dataVal;
            }
          }

          if (eventType === "token") {
            try {
              const parsed = JSON.parse(eventData);
              const text = parsed.text || "";
              setMessages((prev) => {
                const next = [...prev];
                const lastIdx = next.length - 1;
                if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
                  next[lastIdx] = {
                    ...next[lastIdx],
                    content: next[lastIdx].content + text,
                  };
                }
                return next;
              });
              // Yield to let React and the browser paint the text changes
              await nextFrame();
            } catch (e) {
              console.error("Failed to parse token event", e);
            }
          } else if (eventType === "error") {
            try {
              const parsed = JSON.parse(eventData);
              const errorMsg = parsed.message || "未知錯誤";
              setMessages((prev) => {
                const next = [...prev];
                const lastIdx = next.length - 1;
                if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
                  next[lastIdx] = {
                    ...next[lastIdx],
                    error: errorMsg,
                  };
                }
                return next;
              });
            } catch (e) {
              console.error("Failed to parse error event", e);
            }
          } else if (eventType === "done") {
            // Done event terminates streaming immediately
            await reader.cancel().catch(() => {});
            setStreaming(false);
            abortControllerRef.current = null;
            return;
          }
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
      }
      const errorMsg = err.message || "連線發生錯誤，請稍後重試。";
      setMessages((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
          next[lastIdx] = {
            ...next[lastIdx],
            error: errorMsg,
          };
        }
        return next;
      });
    } finally {
      setStreaming(false);
      abortControllerRef.current = null;
    }
  }

  return { messages, streaming, send, abort };
}
