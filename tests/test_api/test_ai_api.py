"""Tests for AI API endpoints — Phase 15-B dynamic status and SSE streaming."""

from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_advisor
from api.main import app
from src.ai.advisor import AIAdvisor

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/ai/status
# ---------------------------------------------------------------------------


def test_status_disabled() -> None:
    mock_config = {"ai": {"enabled": False, "provider": "openai"}}
    mock_secrets = {"openai": False}
    with patch("api.routers.ai.get_config", return_value=mock_config), \
         patch("api.routers.ai.get_secrets_status", return_value=mock_secrets):
        response = client.get("/api/ai/status")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert body["reason"] == "ai_disabled"
        assert body["message"] == "AI 功能已關閉（ai.enabled=false）。"


def test_status_missing_key() -> None:
    mock_config = {"ai": {"enabled": True, "provider": "openai"}}
    mock_secrets = {"openai": False}
    with patch("api.routers.ai.get_config", return_value=mock_config), \
         patch("api.routers.ai.get_secrets_status", return_value=mock_secrets):
        response = client.get("/api/ai/status")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert body["reason"] == "missing_key"
        assert "openai" in body["message"].lower()


def test_status_enabled_with_key() -> None:
    mock_config = {"ai": {"enabled": True, "provider": "openai", "model": "gpt-4o-mini"}}
    mock_secrets = {"openai": True}
    with patch("api.routers.ai.get_config", return_value=mock_config), \
         patch("api.routers.ai.get_secrets_status", return_value=mock_secrets):
        response = client.get("/api/ai/status")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["reason"] == "ok"
        assert body["message"] == "OK"


# ---------------------------------------------------------------------------
# POST /api/ai/chat
# ---------------------------------------------------------------------------


def test_get_advisor_dependency_overrideable() -> None:
    class MockAdvisor:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {"event": "token", "text": "mocked response"}

    app.dependency_overrides[get_advisor] = lambda: MockAdvisor()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert response.status_code == 200
        lines = [line.strip() for line in response.iter_lines() if line]
        assert any("mocked response" in line for line in lines)
    finally:
        app.dependency_overrides.clear()


def test_chat_messages_schema_validation() -> None:
    response = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "bad", "content": "hello"}]},
    )
    assert response.status_code == 422


def test_ai_chat_streaming() -> None:
    class DummyAdvisor:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {"event": "token", "text": "Hello"}
            yield {"event": "token", "text": " world"}

    app.dependency_overrides[get_advisor] = lambda: DummyAdvisor()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "2330 的 RSI？"}]},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Parse SSE lines
        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                event_type = line_str[len("event:"):].strip()
                events.append({"event": event_type})
            elif line_str.startswith("data:"):
                data_val = json.loads(line_str[len("data:"):].strip())
                events[-1]["data"] = data_val

        assert len(events) == 3
        assert events[0]["event"] == "token"
        assert events[0]["data"]["text"] == "Hello"
        assert events[1]["event"] == "token"
        assert events[1]["data"]["text"] == " world"
        assert events[2]["event"] == "done"
    finally:
        app.dependency_overrides.clear()


def test_ai_chat_error_handling() -> None:
    class FailureAdvisor:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            raise RuntimeError("API failure")
            yield {}  # unreachable dummy yield to make it an async generator

    app.dependency_overrides[get_advisor] = lambda: FailureAdvisor()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                events.append({"event": line_str[len("event:"):].strip()})
            elif line_str.startswith("data:"):
                events[-1]["data"] = json.loads(line_str[len("data:"):].strip())

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert "API failure" in events[0]["data"]["message"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/ai/analyze — regression: still returns 503 when AI disabled
# ---------------------------------------------------------------------------


def test_ai_analyze_returns_503_when_ai_disabled() -> None:
    from src.services.dashboard_service import DashboardPayload
    from src.analysis.pattern import MultiTimeframeAnalysis, TimeframeTrend
    import pandas as pd

    mtf = MultiTimeframeAnalysis(
        daily=TimeframeTrend("daily", "多頭", "強"),
        weekly=TimeframeTrend("weekly", "多頭", "強"),
        monthly=TimeframeTrend("monthly", "多頭", "強"),
    )
    dummy_payload = DashboardPayload(
        symbol="2330",
        market="tw",
        daily_df=pd.DataFrame(),
        technical=None,
        candle_patterns=[],
        chart_patterns=[],
        multi_timeframe=mtf,
        ai_enabled=False,
    )
    with patch("api.routers.ai.build_dashboard_payload", return_value=dummy_payload):
        response = client.post(
            "/api/ai/analyze",
            json={"symbol": "2330", "market": "tw"},
        )
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["error"]["code"] == "AI_DISABLED"


def test_ai_chat_streaming_with_tools() -> None:
    class DummyAdvisorWithTools:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {"event": "tool_call", "name": "calculate_indicators", "arguments": {"symbol": "2330", "indicators": ["RSI_14"]}}
            yield {"event": "tool_result", "name": "calculate_indicators", "output_summary": "RSI=68.5"}
            yield {"event": "token", "text": "AI text response"}

    app.dependency_overrides[get_advisor] = lambda: DummyAdvisorWithTools()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "RSI?"}]},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                event_type = line_str[len("event:"):].strip()
                events.append({"event": event_type})
            elif line_str.startswith("data:"):
                data_val = json.loads(line_str[len("data:"):].strip())
                events[-1]["data"] = data_val

        assert len(events) == 4
        assert events[0]["event"] == "tool_call"
        assert events[0]["data"]["name"] == "calculate_indicators"
        assert events[0]["data"]["arguments"]["symbol"] == "2330"

        assert events[1]["event"] == "tool_result"
        assert events[1]["data"]["name"] == "calculate_indicators"
        assert events[1]["data"]["output_summary"] == "RSI=68.5"

        assert events[2]["event"] == "token"
        assert events[2]["data"]["text"] == "AI text response"

        assert events[3]["event"] == "done"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Phase 15-E: AI Q&A investment return tool (calculate_total_return) API & SSE tests
# ---------------------------------------------------------------------------


def test_chat_sse_calculate_total_return_tool_call() -> None:
    class DummyAdvisorWithTotalReturnTool:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {
                "event": "tool_call",
                "name": "calculate_total_return",
                "arguments": {
                    "symbols": ["2330"],
                    "start_date": "2025-01-02",
                    "end_date": "2025-03-31",
                    "initial_amount": 100000.0,
                }
            }

    app.dependency_overrides[get_advisor] = lambda: DummyAdvisorWithTotalReturnTool()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "計算 2330 報酬"}]},
        )
        assert response.status_code == 200

        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                events.append({"event": line_str[len("event:"):].strip()})
            elif line_str.startswith("data:"):
                events[-1]["data"] = json.loads(line_str[len("data:"):].strip())

        assert len(events) == 2
        assert events[0]["event"] == "tool_call"
        assert events[0]["data"]["name"] == "calculate_total_return"
        assert events[0]["data"]["arguments"]["symbols"] == ["2330"]
        assert events[1]["event"] == "done"
    finally:
        app.dependency_overrides.clear()


def test_chat_sse_calculate_total_return_tool_result_summary() -> None:
    class DummyAdvisorWithTotalReturnResult:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {
                "event": "tool_result",
                "name": "calculate_total_return",
                "output_summary": "已完成 1 檔含息報酬試算；0 檔失敗"
            }

    app.dependency_overrides[get_advisor] = lambda: DummyAdvisorWithTotalReturnResult()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "計算 2330 報酬"}]},
        )
        assert response.status_code == 200

        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                events.append({"event": line_str[len("event:"):].strip()})
            elif line_str.startswith("data:"):
                events[-1]["data"] = json.loads(line_str[len("data:"):].strip())

        assert len(events) == 2
        assert events[0]["event"] == "tool_result"
        assert events[0]["data"]["name"] == "calculate_total_return"
        assert events[0]["data"]["output_summary"] == "已完成 1 檔含息報酬試算；0 檔失敗"
        assert events[1]["event"] == "done"
    finally:
        app.dependency_overrides.clear()


def test_chat_sse_calculate_total_return_partial_symbol_error_done() -> None:
    class DummyAdvisorWithPartialError:
        async def stream_chat(self, messages: list[dict]) -> AsyncIterator[dict]:
            yield {
                "event": "tool_result",
                "name": "calculate_total_return",
                "output_summary": "已完成 1 檔含息報酬試算；1 檔失敗"
            }
            yield {
                "event": "token",
                "text": "計算完成，其中 9999 失敗。"
            }

    app.dependency_overrides[get_advisor] = lambda: DummyAdvisorWithPartialError()
    try:
        response = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "計算 2330, 9999"}]},
        )
        assert response.status_code == 200

        events = []
        for line in response.iter_lines():
            line_str = line.decode("utf-8").strip() if isinstance(line, bytes) else str(line).strip()
            if line_str.startswith("event:"):
                events.append({"event": line_str[len("event:"):].strip()})
            elif line_str.startswith("data:"):
                events[-1]["data"] = json.loads(line_str[len("data:"):].strip())

        assert len(events) == 3
        assert events[0]["event"] == "tool_result"
        assert events[0]["data"]["output_summary"] == "已完成 1 檔含息報酬試算；1 檔失敗"
        assert events[1]["event"] == "token"
        assert events[1]["data"]["text"] == "計算完成，其中 9999 失敗。"
        assert events[2]["event"] == "done"
    finally:
        app.dependency_overrides.clear()
