// Tests for MessageBubble component (Phase 10-F-1)

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MessageBubble } from "@/components/ai/message-bubble";

describe("MessageBubble", () => {
  it("renders user bubble with testid", () => {
    render(<MessageBubble role="user" content="你好" />);
    expect(screen.getByTestId("message-bubble-user")).toBeInTheDocument();
  });

  it("renders assistant bubble with testid", () => {
    render(<MessageBubble role="assistant" content="你好" />);
    expect(screen.getByTestId("message-bubble-assistant")).toBeInTheDocument();
  });

  it("shows 你 label for user", () => {
    render(<MessageBubble role="user" content="test" />);
    expect(screen.getByText("你")).toBeInTheDocument();
  });

  it("shows AI label for assistant", () => {
    render(<MessageBubble role="assistant" content="test" />);
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("renders bold markdown (**text**)", () => {
    render(<MessageBubble role="assistant" content="RSI 為 **62.4**" />);
    const bold = screen.getByText("62.4");
    expect(bold.tagName).toBe("STRONG");
  });

  it("renders list markdown (- item)", () => {
    render(<MessageBubble role="assistant" content={"- 項目一\n- 項目二"} />);
    expect(screen.getByText("項目一")).toBeInTheDocument();
    expect(screen.getByText("項目二")).toBeInTheDocument();
  });

  it("renders inline code (`code`)", () => {
    render(<MessageBubble role="assistant" content="使用 `RSI_14` 指標" />);
    expect(screen.getByText("RSI_14")).toBeInTheDocument();
  });

  it("shows pulsing thinking text when content is empty (streaming placeholder)", () => {
    render(<MessageBubble role="assistant" content="" />);
    const placeholder = screen.getByTestId("chat-thinking-placeholder");
    expect(placeholder).toHaveTextContent("思考中...");
    expect(placeholder).toHaveClass("animate-pulse");
  });

  it("user bubble aligns right (items-end)", () => {
    render(<MessageBubble role="user" content="hi" />);
    const bubble = screen.getByTestId("message-bubble-user");
    expect(bubble.className).toMatch(/items-end/);
  });

  it("assistant bubble aligns left (items-start)", () => {
    render(<MessageBubble role="assistant" content="hi" />);
    const bubble = screen.getByTestId("message-bubble-assistant");
    expect(bubble.className).toMatch(/items-start/);
  });
});
