from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

import src.ai.advisor as advisor_module
from src.ai.advisor import (
    AIAdvisor,
    AnthropicAdapter,
    DISCLAIMER,
    GeminiAdapter,
    OpenAIAdapter,
)
from src.core.constants import STANDARD_COLUMNS, TAIPEI_TZ
from src.core.config import clear_config_cache, get_config


def _make_daily_df(symbol: str = "2330", periods: int = 120) -> pd.DataFrame:
    idx = pd.date_range(start="2025-01-01", periods=periods, freq="D", tz=TAIPEI_TZ)
    return pd.DataFrame(
        {
            "date": pd.Series(idx).astype(f"datetime64[ns, {TAIPEI_TZ}]"),
            "open": [100.0 + i for i in range(periods)],
            "high": [101.0 + i for i in range(periods)],
            "low": [99.0 + i for i in range(periods)],
            "close": [100.5 + i for i in range(periods)],
            "volume": [1000 + i for i in range(periods)],
            "symbol": [symbol] * periods,
        }
    )[STANDARD_COLUMNS]


@dataclass
class StubStorage:
    daily: pd.DataFrame
    minute: pd.DataFrame | None = None

    def load_daily(self, symbol: str, market: str = "tw") -> pd.DataFrame:
        if self.daily.empty:
            return self.daily.copy(deep=True)
        return self.daily[self.daily["symbol"] == symbol].copy(deep=True)

    def load_minute(self, symbol: str, market: str = "tw") -> pd.DataFrame:
        if self.minute is None:
            return pd.DataFrame(columns=STANDARD_COLUMNS)
        if self.minute.empty:
            return self.minute.copy(deep=True)
        return self.minute[self.minute["symbol"] == symbol].copy(deep=True)


class StubAdapter:
    provider_name = "stub"

    def __init__(self, responses: list[dict[str, Any]]):
        self._responses = responses
        self.model = "stub-model"

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._responses:
            return self._responses.pop(0)
        return {"text": "", "tool_calls": []}


def test_tool_dispatch() -> None:
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    result = advisor._execute_tool("get_price_data", {"symbol": "2330", "period": "3mo"})
    assert isinstance(result, dict)
    assert result["symbol"] == "2330"
    assert result["data_count"] > 0


def test_unknown_tool_returns_error() -> None:
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    result = advisor._execute_tool("nonexistent", {})
    assert result["error"].startswith("Unknown tool:")


def test_disclaimer_always_appended() -> None:
    responses = [
        {
            "text": "",
            "tool_calls": [
                {"id": "call-1", "name": "get_price_data", "arguments": {"symbol": "2330", "period": "3mo"}}
            ],
        },
        {"text": "這是分析內容。", "tool_calls": []},
    ]
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter(responses),
    )

    answer = advisor.ask("2330 的 RSI 怎麼看？")
    assert "這是分析內容" in answer
    assert "免責聲明" in answer


def test_invalid_symbol_returns_error() -> None:
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(pd.DataFrame(columns=STANDARD_COLUMNS)),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    result = advisor._handle_get_price_data(symbol="9999", period="3mo")
    assert "error" in result


@pytest.mark.parametrize(
    ("provider", "secrets", "adapter_cls"),
    [
        ("anthropic", {"anthropic_api_key": "test-key"}, AnthropicAdapter),
        ("openai", {"openai_api_key": "test-key"}, OpenAIAdapter),
        ("gemini", {"gemini_api_key": "test-key"}, GeminiAdapter),
    ],
)
def test_ai_provider_selected_from_config(monkeypatch, provider: str, secrets: dict[str, str], adapter_cls: type) -> None:
    monkeypatch.setattr(
        advisor_module,
        "get_config",
        lambda: {"ai": {"enabled": True, "provider": provider, "model": "model-from-config"}, "secrets": secrets},
    )
    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    assert advisor.provider == provider
    assert isinstance(advisor.provider_adapter, adapter_cls)


def test_ai_model_passed_to_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        advisor_module,
        "get_config",
        lambda: {
            "ai": {"enabled": True, "provider": "openai", "model": "gpt-test-model"},
            "secrets": {"openai_api_key": "k"},
        },
    )
    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    assert advisor.model == "gpt-test-model"
    assert advisor.provider_adapter is not None
    assert advisor.provider_adapter.model == "gpt-test-model"


def test_ai_provider_missing_api_key_returns_error(monkeypatch) -> None:
    monkeypatch.setattr(
        advisor_module,
        "get_config",
        lambda: {"ai": {"enabled": True, "provider": "openai", "model": "gpt-test-model"}, "secrets": {}},
    )
    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    answer = advisor.ask("請分析 2330")
    assert "Missing API key" in answer
    assert "免責聲明" in answer


def test_ai_disabled_does_not_require_provider_or_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        advisor_module,
        "get_config",
        lambda: {"ai": {"enabled": False, "provider": "openai", "model": "gpt-test-model"}, "secrets": {}},
    )
    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    assert advisor.enabled is False
    assert advisor.provider_adapter is None
    answer = advisor.ask("請分析 2330")
    assert answer == "AI 功能已關閉（ai.enabled=false）。"


def test_ai_tool_call_normalized_across_providers(monkeypatch) -> None:
    monkeypatch.setattr(AnthropicAdapter, "__init__", lambda self, api_key, model, timeout_seconds=30.0: None)
    anthropic_adapter = AnthropicAdapter(api_key="", model="")
    openai_adapter = OpenAIAdapter(api_key="", model="")
    gemini_adapter = GeminiAdapter(api_key="", model="")

    anthropic_payload = {
        "content": [{"type": "tool_use", "id": "tool-1", "name": "get_price_data", "input": {"symbol": "2330"}}]
    }
    openai_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "type": "function",
                            "function": {"name": "get_price_data", "arguments": "{\"symbol\": \"2330\"}"},
                        }
                    ]
                }
            }
        ]
    }
    gemini_payload = {
        "candidates": [{"content": {"parts": [{"functionCall": {"id": "tool-1", "name": "get_price_data", "args": {"symbol": "2330"}}}]}}]
    }

    anthropic_calls = anthropic_adapter.normalize_tool_calls(anthropic_payload)
    openai_calls = openai_adapter.normalize_tool_calls(openai_payload)
    gemini_calls = gemini_adapter.normalize_tool_calls(gemini_payload)

    assert anthropic_calls[0].name == openai_calls[0].name == gemini_calls[0].name == "get_price_data"
    assert anthropic_calls[0].arguments == openai_calls[0].arguments == gemini_calls[0].arguments == {"symbol": "2330"}


@pytest.mark.integration
def test_real_api_call() -> None:
    clear_config_cache()
    config = get_config()
    ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
    secrets = config.get("secrets", {}) if isinstance(config, dict) else {}

    if not bool(ai_section.get("enabled", True)):
        pytest.skip("AI is disabled in config (ai.enabled=false).")

    provider = str(ai_section.get("provider", "anthropic")).strip().lower()

    if provider == "anthropic":
        has_key = bool(str(secrets.get("anthropic_api_key", "")).strip())
    elif provider == "openai":
        has_key = bool(str(secrets.get("openai_api_key", "")).strip())
    elif provider == "gemini":
        has_key = bool(str(secrets.get("gemini_api_key", "") or secrets.get("google_api_key", "")).strip())
    else:
        pytest.skip(f"Unsupported provider in config: {provider}")

    if not has_key:
        pytest.skip(f"{provider} API key is not configured.")

    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    reply = advisor.ask("請用一句話解釋 RSI 指標是什麼。")

    if reply.startswith("AI provider request failed:"):
        pytest.skip(reply)

    assert isinstance(reply, str)
    assert "免責聲明" in reply
    assert len(reply.strip()) > len(DISCLAIMER.strip())
