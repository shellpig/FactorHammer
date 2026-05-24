import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAIChat, toApiMessages, Message } from "@/hooks/use-ai-chat";

// Mock helper to build a ReadableStream Response
function mockSseResponse(chunks: string[]) {
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("toApiMessages and useAIChat 14-Test Suite", () => {
  let fetchSpy: any;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. toApiMessages - filters out greeting by content and isGreeting flag
  it("1. toApiMessages - filters out greeting by content and isGreeting flag", () => {
    const greetingMsg: Message = {
      role: "assistant",
      content: "你好。可提問範例：2330 的 RSI 是多少？／回測 KD_Cross 在 2020 年的表現？",
      isGreeting: true,
    };
    const validUserMsg: Message = {
      role: "user",
      content: "真實問題",
    };
    expect(toApiMessages([greetingMsg, validUserMsg])).toEqual([
      { role: "user", content: "真實問題" },
    ]);
  });

  // 2. toApiMessages - filters out empty or whitespace-only messages
  it("2. toApiMessages - filters out empty or whitespace-only messages", () => {
    const emptyMsg1: Message = { role: "assistant", content: "" };
    const emptyMsg2: Message = { role: "user", content: "   " };
    const validMsg: Message = { role: "user", content: "valid content" };
    expect(toApiMessages([emptyMsg1, emptyMsg2, validMsg])).toEqual([
      { role: "user", content: "valid content" },
    ]);
  });

  // 3. toApiMessages - filters out other non-API entries (e.g., handles roles and invalid structures)
  it("3. toApiMessages - filters out other non-API entries", () => {
    const invalidRoleMsg = { role: "system" as any, content: "system text" };
    const validMsg: Message = { role: "assistant", content: "assistant text" };
    expect(toApiMessages([invalidRoleMsg, validMsg])).toEqual([
      { role: "assistant", content: "assistant text" },
    ]);
  });

  // 4. toApiMessages - maps valid user and assistant messages properly
  it("4. toApiMessages - maps valid user and assistant messages properly", () => {
    const messages: Message[] = [
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
    ];
    expect(toApiMessages(messages)).toEqual([
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
    ]);
  });

  // 5. useAIChat - has greeting by default and is not streaming
  it("5. useAIChat - has greeting by default and is not streaming", () => {
    const { result } = renderHook(() => useAIChat());
    expect(result.current.messages.length).toBe(1);
    expect(result.current.messages[0].isGreeting).toBe(true);
    expect(result.current.streaming).toBe(false);
  });

  // 6. useAIChat - send() triggers fetch with correct POST schema and headers
  it("6. useAIChat - send() triggers fetch with correct POST schema and headers", async () => {
    fetchSpy.mockResolvedValue(mockSseResponse(["event: done\ndata: {}\n\n"]));
    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("hello");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/ai/chat"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          messages: [{ role: "user", content: "hello" }],
        }),
      })
    );
  });

  // 7. useAIChat - streams tokens correctly on successful fetch
  it("7. useAIChat - streams tokens correctly on successful fetch", async () => {
    fetchSpy.mockResolvedValue(
      mockSseResponse([
        "event: token\ndata: {\"text\": \"hello\"}\n\n",
        "event: token\ndata: {\"text\": \" world\"}\n\n",
        "event: done\ndata: {}\n\n",
      ])
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("MACD是什麼");
    });

    expect(result.current.streaming).toBe(true);
    await waitFor(() => expect(result.current.streaming).toBe(false));

    expect(result.current.messages[2].content).toBe("hello world");
  });

  // 8. useAIChat - CRLF (\r\n) normalization in the SSE parser
  it("8. useAIChat - CRLF (\\r\\n) normalization in the SSE parser", async () => {
    fetchSpy.mockResolvedValue(
      mockSseResponse([
        "event: token\r\ndata: {\"text\": \"CRLF text\"}\r\n\r\n",
        "event: done\r\ndata: {}\r\n\r\n",
      ])
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("CRLF test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages[2].content).toBe("CRLF text");
  });

  // 9. useAIChat - supports multi-line data concatenation
  it("9. useAIChat - supports multi-line data concatenation", async () => {
    fetchSpy.mockResolvedValue(
      mockSseResponse([
        "event: token\ndata: {\"text\":\ndata: \"multi-line\"}\n\n",
        "event: done\ndata: {}\n\n",
      ])
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("multi-line test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages[2].content).toBe("multi-line");
  });

  // 10. useAIChat - done event terminates streaming immediately
  it("10. useAIChat - done event terminates streaming immediately", async () => {
    // We send done event before stream is actually closed by server
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: token\ndata: {\"text\": \"before done\"}\n\n"));
        controller.enqueue(new TextEncoder().encode("event: done\ndata: {}\n\n"));
        // Following token should not be parsed because loop returned on done
        controller.enqueue(new TextEncoder().encode("event: token\ndata: {\"text\": \"after done\"}\n\n"));
      },
    });
    fetchSpy.mockResolvedValue(new Response(stream));

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("done test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages[2].content).toBe("before done");
  });

  // 11. useAIChat - handles event: error from SSE stream
  it("11. useAIChat - handles event: error from SSE stream", async () => {
    fetchSpy.mockResolvedValue(
      mockSseResponse([
        "event: error\ndata: {\"message\": \"API Key error\"}\n\n",
      ])
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("error event test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages[2].error).toBe("API Key error");
  });

  // 12. useAIChat - handles fetch non-ok response errors
  it("12. useAIChat - handles fetch non-ok response errors", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ detail: { error: { message: "Internal Error" } } }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      })
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("http error test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages[2].error).toBe("Internal Error");
  });

  // 13. useAIChat - supports aborting/cancelling the stream
  it("13. useAIChat - supports aborting/cancelling the stream", async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: token\ndata: {\"text\": \"aborted\"}\n\n"));
      },
    });
    fetchSpy.mockResolvedValue(new Response(stream));

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("abort test");
    });

    await waitFor(() => expect(result.current.messages[2].content).toBe("aborted"));
    expect(result.current.streaming).toBe(true);

    act(() => {
      result.current.abort();
    });

    expect(result.current.streaming).toBe(false);
  });

  // 14. useAIChat - yields to render frame between multiple tokens in a single chunk (regression test)
  it("14. useAIChat - yields to render frame between multiple tokens in a single chunk", async () => {
    const rafSpy = vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });

    fetchSpy.mockResolvedValue(
      mockSseResponse([
        "event: token\ndata: {\"text\": \"A\"}\n\nevent: token\ndata: {\"text\": \"B\"}\n\nevent: done\ndata: {}\n\n",
      ])
    );

    const { result } = renderHook(() => useAIChat());

    act(() => {
      result.current.send("raf test");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));

    expect(result.current.messages[2].content).toBe("AB");
    // Verifies requestAnimationFrame was triggered twice (once per token)
    expect(rafSpy).toHaveBeenCalledTimes(2);

    rafSpy.mockRestore();
  });
});
