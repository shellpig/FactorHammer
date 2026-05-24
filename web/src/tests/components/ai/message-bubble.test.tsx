// Tests for MessageBubble component (Phase 10-F-1)

import { render, screen, fireEvent } from "@testing-library/react";
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

  it("renders tool chips when toolCalls are present", () => {
    const toolCalls = [
      {
        name: "calculate_indicators",
        arguments: { symbol: "2330" },
        result: { output_summary: "RSI=68.5" }
      }
    ];
    render(<MessageBubble role="assistant" content="Let me check." toolCalls={toolCalls} />);
    expect(screen.getByTestId("tool-chips-container")).toBeInTheDocument();
    expect(screen.getByText("已更新並分析 2330 日線資料")).toBeInTheDocument();
    expect(screen.getByTestId("tool-chip-summary")).toHaveTextContent("回傳：RSI=68.5");
  });

  it("can toggle ToolCallChip open to show details", () => {
    const toolCalls = [
      {
        name: "calculate_indicators",
        arguments: { symbol: "2330" },
        result: { output_summary: "RSI=68.5" }
      }
    ];
    render(<MessageBubble role="assistant" content="Let me check." toolCalls={toolCalls} />);
    const toggle = screen.getByTestId("tool-chip-toggle");
    expect(screen.queryByTestId("tool-chip-details")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByTestId("tool-chip-details")).toBeInTheDocument();
    expect(screen.getByText(/"symbol": "2330"/)).toBeInTheDocument();
  });

  it("renders calculate_total_return chip in processing state with correct statusText", () => {
    const toolCalls = [
      {
        name: "calculate_total_return",
        arguments: { symbols: ["2330", "0050"] }
      }
    ];
    render(<MessageBubble role="assistant" content="Calculating..." toolCalls={toolCalls} />);
    expect(screen.getByText("正在分析 2330, 0050 的含息總報酬率...")).toBeInTheDocument();
  });

  it("renders calculate_total_return chip in done state with correct statusText", () => {
    const toolCalls = [
      {
        name: "calculate_total_return",
        arguments: { symbols: ["2330"] },
        result: { output_summary: "已完成 1 檔含息報酬試算；0 檔失敗" }
      }
    ];
    render(<MessageBubble role="assistant" content="Calculation complete." toolCalls={toolCalls} />);
    expect(screen.getByText("已完成 2330 的含息總報酬率計算")).toBeInTheDocument();
  });

  it("handles symbols as a string gracefully without crashing", () => {
    const toolCalls = [
      {
        name: "calculate_total_return",
        arguments: { symbols: "2330, 0050" }
      }
    ];
    render(<MessageBubble role="assistant" content="Calculating..." toolCalls={toolCalls} />);
    expect(screen.getByText("正在分析 2330, 0050 的含息總報酬率...")).toBeInTheDocument();
  });
});
