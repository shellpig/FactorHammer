// Tests for ChatPageClient component (Phase 15-C)
import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ChatPageClient } from "@/components/ai/chat-page-client";
import { useAIChat } from "@/hooks/use-ai-chat";

// scrollIntoView is not implemented in jsdom
window.HTMLElement.prototype.scrollIntoView = vi.fn();

vi.mock("@/hooks/use-ai-chat", () => ({
  useAIChat: vi.fn(),
}));

const mockUseAIChat = useAIChat as any;

beforeEach(() => {
  localStorage.setItem("ai_chat.disclaimer_accepted_v1", "1");
  vi.useFakeTimers();

  // Default mock behavior
  mockUseAIChat.mockReturnValue({
    messages: [
      {
        role: "assistant",
        content: "你好。可提問範例：2330 的 RSI 是多少？／回測 KD_Cross 在 2020 年的表現？",
      },
    ],
    streaming: false,
    send: vi.fn(),
    abort: vi.fn(),
  });
});

afterEach(() => {
  localStorage.clear();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ChatPageClient", () => {
  it("renders chat page container", () => {
    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  it("shows greeting message on load", async () => {
    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });
    expect(screen.getByText(/可提問範例/)).toBeInTheDocument();
  });

  it("calls send with input when send button clicked", () => {
    const sendMock = vi.fn();
    mockUseAIChat.mockReturnValue({
      messages: [{ role: "assistant", content: "你好" }],
      streaming: false,
      send: sendMock,
      abort: vi.fn(),
    });

    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });

    const input = screen.getByTestId("chat-input-field");
    fireEvent.change(input, { target: { value: "2330 的 RSI？" } });
    fireEvent.click(screen.getByTestId("chat-send-button"));

    expect(sendMock).toHaveBeenCalledWith("2330 的 RSI？");
  });

  it("empty or whitespace-only input does not trigger send", () => {
    const sendMock = vi.fn();
    mockUseAIChat.mockReturnValue({
      messages: [{ role: "assistant", content: "你好" }],
      streaming: false,
      send: sendMock,
      abort: vi.fn(),
    });

    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });

    const input = screen.getByTestId("chat-input-field");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByTestId("chat-send-button"));

    expect(sendMock).not.toHaveBeenCalled();
  });

  it("Enter key triggers send", () => {
    const sendMock = vi.fn();
    mockUseAIChat.mockReturnValue({
      messages: [{ role: "assistant", content: "你好" }],
      streaming: false,
      send: sendMock,
      abort: vi.fn(),
    });

    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });

    const input = screen.getByTestId("chat-input-field");
    fireEvent.change(input, { target: { value: "Enter 送出" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMock).toHaveBeenCalledWith("Enter 送出");
  });

  it("shows cancel button and calls abort when streaming", () => {
    const abortMock = vi.fn();
    mockUseAIChat.mockReturnValue({
      messages: [
        { role: "user", content: "MACD是什麼" },
        { role: "assistant", content: "正在運算..." },
      ],
      streaming: true,
      send: vi.fn(),
      abort: abortMock,
    });

    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });

    const cancelBtn = screen.getByTestId("chat-cancel-button");
    expect(cancelBtn).toBeInTheDocument();
    expect(cancelBtn.textContent).toBe("取消");

    fireEvent.click(cancelBtn);
    expect(abortMock).toHaveBeenCalled();
  });

  it("renders error inside MessageBubble when error present", () => {
    mockUseAIChat.mockReturnValue({
      messages: [
        { role: "user", content: "測試錯誤" },
        { role: "assistant", content: "一部分內容", error: "連線中斷" },
      ],
      streaming: false,
      send: vi.fn(),
      abort: vi.fn(),
    });

    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });

    const errorBubble = screen.getByTestId("chat-inline-error");
    expect(errorBubble).toBeInTheDocument();
    expect(errorBubble.textContent).toContain("連線中斷");
  });

  it("shows disclaimer gate when localStorage key absent", () => {
    localStorage.clear();
    render(<ChatPageClient />);
    act(() => { vi.runAllTimers(); });
    expect(screen.getByTestId("disclaimer-gate")).toBeInTheDocument();
  });
});
