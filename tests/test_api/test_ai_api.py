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
