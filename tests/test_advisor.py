from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import src.ai.advisor as advisor_module
import src.core.config as _config_module
from src.ai.advisor import (
    AIAdvisor,
    AnthropicAdapter,
    BaseProviderAdapter,
    DashboardAnalysis,
    DeepSeekAdapter,
    DISCLAIMER,
    GeminiAdapter,
    OpenAIAdapter,
)
from src.analysis.chip_analysis import ChipSummary
from src.analysis.technical_summary import PriceLevel, TechnicalSummary
from src.core.constants import STANDARD_COLUMNS, TAIPEI_TZ
from src.core.config import clear_config_cache, get_config
from src.core.exceptions import AICallError, AIDisabledError


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


def _make_technical_summary() -> TechnicalSummary:
    return TechnicalSummary(
        trend_direction="多頭趨勢",
        ma_status="多頭排列 (5>20>60)",
        kd_status="KD 多方",
        macd_status="正值擴張",
        volume_status="量能放大",
        volume_price_relation="價漲量增",
        short_term_score=0.78,
        short_term_label="強勢偏多",
        short_term_components={"ma": 0.9, "kd": 0.7, "volume_price": 0.8, "breakout": 0.7},
        resistance_levels=[PriceLevel(value=860.0, label="近20日高點", kind="resistance")],
        support_levels=[PriceLevel(value=810.0, label="MA20", kind="support")],
        volume_price_divergence="量價同步",
        ma_bias="與 MA20 乖離約 +2.11%，中性",
        chip_behavior="法人偏多",
        operation_observation="偏多但需留意追價風險",
    )


def _make_chip_summary() -> ChipSummary:
    return ChipSummary(
        foreign_net_n_days=36,
        trust_net_n_days=10,
        dealer_net_n_days=5,
        foreign_label="買超 36 張",
        trust_label="買超 10 張",
        dealer_label="買超 5 張",
        chip_concentration="集中",
        chip_trend="中性偏多",
        chip_description="法人進場延續",
        margin_balance_change=120,
        short_balance_change=-30,
    )


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
        response_format: dict[str, Any] | None = None,
        thinking: dict[str, Any] | None = None,
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


def test_dashboard_analysis_returns_correct_structure() -> None:
    payload = {
        "industry_overview": ["半導體景氣回升", "AI 需求延續", "供應鏈庫存改善"],
        "company_overview": ["先進製程市占領先", "資本支出維持高檔", "毛利率維持穩健"],
        "volume_price_analysis": "量價同步偏多，短線波動仍存在。",
        "scenarios": [
            {"name": "開高走高", "entry_range": "850 ~ 855", "stop_loss": 838.0, "target": "868 / 880"},
            {"name": "震盪整理", "entry_range": "840 ~ 848", "stop_loss": 832.0, "target": "858 / 868"},
            {"name": "開低回測", "entry_range": "832 ~ 838", "stop_loss": 825.0, "target": "848 / 858"},
        ],
        "conclusion": "整體偏多但需控管回檔風險。",
    }
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": json.dumps(payload, ensure_ascii=False), "tool_calls": []}]),
    )
    result = advisor.generate_stock_dashboard_analysis(
        symbol="2330",
        technical_summary=_make_technical_summary(),
        chip_summary=_make_chip_summary(),
        company_info={"industry_category": "半導體"},
        recent_prices=_make_daily_df(),
    )
    assert isinstance(result, DashboardAnalysis)
    assert len(result.industry_overview) >= 3
    assert len(result.company_overview) >= 3
    assert isinstance(result.volume_price_analysis, str) and result.volume_price_analysis
    assert isinstance(result.conclusion, str) and result.conclusion


def test_dashboard_analysis_us_prompt_includes_market_currency_and_traditional_chinese_rule() -> None:
    class RecordingAdapter:
        provider_name = "stub"

        def __init__(self):
            self.model = "stub-model"
            self.last_system_prompt = ""
            self.last_messages: list[dict[str, Any]] = []

        def complete(
            self,
            *,
            model: str,
            system_prompt: str,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
        ) -> dict[str, Any]:
            self.last_system_prompt = system_prompt
            self.last_messages = messages
            payload = {
                "industry_overview": ["A", "B", "C"],
                "company_overview": ["D", "E", "F"],
                "volume_price_analysis": "X",
                "scenarios": [
                    {"name": "情境1", "entry_range": "1", "stop_loss": 1.0, "target": "2"},
                    {"name": "情境2", "entry_range": "2", "stop_loss": 2.0, "target": "3"},
                    {"name": "情境3", "entry_range": "3", "stop_loss": 3.0, "target": "4"},
                ],
                "conclusion": "Y",
            }
            return {"text": json.dumps(payload, ensure_ascii=False), "tool_calls": []}

    adapter = RecordingAdapter()
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df(symbol="BRK-B")),
        adapter=adapter,
    )
    advisor.generate_stock_dashboard_analysis(
        symbol="brk.b",
        technical_summary=_make_technical_summary(),
        chip_summary=None,
        company_info=None,
        recent_prices=_make_daily_df(symbol="BRK-B"),
        market="us",
        currency="USD",
    )
    user_prompt = adapter.last_messages[0]["content"]
    assert '"symbol": "BRK-B"' in user_prompt
    assert '"market": "us"' in user_prompt
    assert '"currency": "USD"' in user_prompt
    assert "You must reply entirely in Traditional Chinese (zh-TW)." in user_prompt


def test_dashboard_analysis_rejects_invalid_us_symbol() -> None:
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df(symbol="AAPL")),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )
    with pytest.raises(AICallError):
        advisor.generate_stock_dashboard_analysis(
            symbol="7203.T",
            technical_summary=_make_technical_summary(),
            chip_summary=None,
            company_info=None,
            recent_prices=_make_daily_df(symbol="AAPL"),
            market="us",
        )


def test_handle_get_price_data_accepts_us_symbol_with_market_context() -> None:
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df(symbol="AAPL")),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )
    result = advisor._handle_get_price_data(symbol="aapl", period="3mo", market="us")
    assert result["symbol"] == "AAPL"
    assert result["data_count"] > 0


def test_dashboard_analysis_scenarios_count() -> None:
    payload = {
        "industry_overview": ["A", "B", "C"],
        "company_overview": ["D", "E", "F"],
        "volume_price_analysis": "X",
        "scenarios": [
            {"name": "情境1", "entry_range": "1", "stop_loss": 1.0, "target": "2"},
            {"name": "情境2", "entry_range": "2", "stop_loss": 2.0, "target": "3"},
            {"name": "情境3", "entry_range": "3", "stop_loss": 3.0, "target": "4"},
        ],
        "conclusion": "Y",
    }
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": json.dumps(payload, ensure_ascii=False), "tool_calls": []}]),
    )
    result = advisor.generate_stock_dashboard_analysis(
        symbol="2330",
        technical_summary=_make_technical_summary(),
        chip_summary=_make_chip_summary(),
        company_info=None,
        recent_prices=_make_daily_df(),
    )
    assert len(result.scenarios) == 3


def test_dashboard_analysis_without_chip() -> None:
    payload = {
        "industry_overview": ["A", "B", "C"],
        "company_overview": ["D", "E", "F"],
        "volume_price_analysis": "X",
        "scenarios": [
            {"name": "情境1", "entry_range": "1", "stop_loss": 1.0, "target": "2"},
            {"name": "情境2", "entry_range": "2", "stop_loss": 2.0, "target": "3"},
            {"name": "情境3", "entry_range": "3", "stop_loss": 3.0, "target": "4"},
        ],
        "conclusion": "Y",
    }
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": json.dumps(payload, ensure_ascii=False), "tool_calls": []}]),
    )
    result = advisor.generate_stock_dashboard_analysis(
        symbol="2330",
        technical_summary=_make_technical_summary(),
        chip_summary=None,
        company_info=None,
        recent_prices=_make_daily_df(),
    )
    assert isinstance(result, DashboardAnalysis)


def test_dashboard_analysis_ai_disabled() -> None:
    advisor = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([]),
    )
    with pytest.raises(AIDisabledError):
        advisor.generate_stock_dashboard_analysis(
            symbol="2330",
            technical_summary=_make_technical_summary(),
            chip_summary=_make_chip_summary(),
            company_info=None,
            recent_prices=_make_daily_df(),
        )


# ---------------------------------------------------------------------------
# Phase 15-A-1: DeepSeek adapter tests
# ---------------------------------------------------------------------------


def test_deepseek_adapter_is_selected_when_provider_deepseek(monkeypatch) -> None:
    monkeypatch.setattr(
        advisor_module,
        "get_config",
        lambda: {
            "ai": {"enabled": True, "provider": "deepseek", "model": "deepseek-v4-flash"},
            "secrets": {"deepseek_api_key": "sk-test-key"},
        },
    )
    advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
    assert advisor.provider == "deepseek"
    assert isinstance(advisor.provider_adapter, DeepSeekAdapter)


def test_deepseek_default_model_is_flash() -> None:
    from src.ai.advisor import DEFAULT_MODELS
    assert DEFAULT_MODELS["deepseek"] == "deepseek-v4-flash"


def test_deepseek_resolve_api_key() -> None:
    advisor = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
    )
    secrets = {"deepseek_api_key": "sk-deepseek-123"}
    key = advisor._resolve_api_key("deepseek", secrets)
    assert key == "sk-deepseek-123"


def test_deepseek_dashboard_passes_response_format_and_thinking(monkeypatch) -> None:
    """generate_stock_dashboard_analysis must pass response_format + thinking to adapter for deepseek."""
    received_kwargs: dict[str, Any] = {}

    class CapturingAdapter:
        provider_name = "deepseek"
        model = "deepseek-v4-flash"

        def complete(self, *, model, system_prompt, messages, tools, response_format=None, thinking=None, **kw):
            received_kwargs["response_format"] = response_format
            received_kwargs["thinking"] = thinking
            payload = {
                "industry_overview": ["A"],
                "company_overview": ["B"],
                "volume_price_analysis": "C",
                "scenarios": [
                    {"name": "s1", "entry_range": "1", "stop_loss": 1.0, "target": "2"},
                    {"name": "s2", "entry_range": "2", "stop_loss": 2.0, "target": "3"},
                    {"name": "s3", "entry_range": "3", "stop_loss": 3.0, "target": "4"},
                ],
                "conclusion": "D",
            }
            return {"text": json.dumps(payload), "tool_calls": []}

    advisor = AIAdvisor(
        enabled=True,
        provider="deepseek",
        model="deepseek-v4-flash",
        storage=StubStorage(_make_daily_df()),
        adapter=CapturingAdapter(),
    )
    advisor.generate_stock_dashboard_analysis(
        symbol="2330",
        technical_summary=_make_technical_summary(),
        chip_summary=None,
        company_info=None,
        recent_prices=_make_daily_df(),
    )
    assert received_kwargs.get("response_format") == {"type": "json_object"}
    assert received_kwargs.get("thinking") == {"type": "disabled"}


def test_deepseek_base_url_differs_from_openai() -> None:
    assert DeepSeekAdapter.DEFAULT_BASE_URL != OpenAIAdapter.DEFAULT_BASE_URL
    assert "deepseek.com" in DeepSeekAdapter.DEFAULT_BASE_URL
    assert "/v1/" not in DeepSeekAdapter.DEFAULT_BASE_URL


def test_deepseek_resolve_api_key_missing_field_returns_empty() -> None:
    advisor = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
    )
    assert advisor._resolve_api_key("deepseek", {}) == ""
    assert advisor._resolve_api_key("deepseek", {"other_key": "sk-x"}) == ""


def test_deepseek_adapter_reads_key_from_env_via_config(monkeypatch, tmp_path) -> None:
    (tmp_path / "config.yaml").write_text("ui:\n  theme: dark\n", encoding="utf-8")
    (tmp_path / ".env").write_text("", encoding="utf-8")
    monkeypatch.setattr(_config_module, "get_project_root", lambda: tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    _config_module.clear_config_cache()
    try:
        advisor = AIAdvisor(provider="deepseek", storage=StubStorage(_make_daily_df()))
        assert advisor._provider_error is None
        assert advisor.provider_adapter is not None
        assert advisor.provider_adapter.api_key == "sk-x"
    finally:
        _config_module.clear_config_cache()


def test_base_adapter_complete_signature_accepts_kwargs() -> None:
    for cls in [BaseProviderAdapter, AnthropicAdapter, OpenAIAdapter, GeminiAdapter, DeepSeekAdapter]:
        params = inspect.signature(cls.complete).parameters
        assert "response_format" in params, f"{cls.__name__}.complete missing response_format"
        assert "thinking" in params, f"{cls.__name__}.complete missing thinking"
        assert params["response_format"].default is None, f"{cls.__name__}.complete response_format must default to None"
        assert params["thinking"].default is None, f"{cls.__name__}.complete thinking must default to None"


def test_anthropic_gemini_ignore_dashboard_kwargs() -> None:
    # Anthropic: response_format / thinking must NOT be forwarded to messages.create
    anthropic_adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    anthropic_adapter.api_key = "test"
    anthropic_adapter.model = "test-model"
    anthropic_adapter.timeout_seconds = 30.0
    mock_create = MagicMock(return_value=MagicMock(content=[]))
    anthropic_adapter._client = MagicMock()
    anthropic_adapter._client.messages.create = mock_create

    anthropic_adapter.complete(
        model="test-model",
        system_prompt="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        response_format={"type": "json_object"},
        thinking={"type": "disabled"},
    )

    call_kwargs = mock_create.call_args.kwargs
    assert "response_format" not in call_kwargs
    assert "thinking" not in call_kwargs

    # Gemini: same — payload sent to requests.post must not include those keys
    gemini_adapter = GeminiAdapter.__new__(GeminiAdapter)
    gemini_adapter.api_key = "test"
    gemini_adapter.model = "gemini-2.0-flash"
    gemini_adapter.timeout_seconds = 30.0

    with patch("src.ai.advisor.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"candidates": []}
        mock_post.return_value = mock_resp

        gemini_adapter.complete(
            model="gemini-2.0-flash",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
        )

        sent_payload = mock_post.call_args.kwargs["json"]
        assert "response_format" not in sent_payload
        assert "thinking" not in sent_payload


def test_openai_adapter_base_url_backward_compat() -> None:
    adapter = OpenAIAdapter(api_key="x", model="y")

    with patch("src.ai.advisor.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok", "tool_calls": None}}]}
        mock_post.return_value = mock_resp

        adapter.complete(
            model="y",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )

        called_url = mock_post.call_args.args[0]
        assert called_url == "https://api.openai.com/v1/chat/completions"


def test_deepseek_adapter_inherits_openai_normalize() -> None:
    adapter = DeepSeekAdapter(api_key="test", model="deepseek-v4-flash")
    openai_format = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-ds-1",
                            "type": "function",
                            "function": {
                                "name": "get_price_data",
                                "arguments": '{"symbol": "2330"}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    result = adapter.normalize_tool_calls(openai_format)
    assert len(result) == 1
    assert result[0].name == "get_price_data"
    assert result[0].arguments == {"symbol": "2330"}
    assert result[0].id == "call-ds-1"


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
