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
    import asyncio
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    async def run():
        result = await advisor._execute_tool("get_price_data", {"symbol": "2330", "period": "3mo"})
        assert isinstance(result, dict)
        assert result["symbol"] == "2330"
        assert result["data_count"] > 0

    asyncio.run(run())


def test_unknown_tool_returns_error() -> None:
    import asyncio
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    async def run():
        result = await advisor._execute_tool("nonexistent", {})
        assert result["error"].startswith("Unknown tool:")

    asyncio.run(run())


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
    import asyncio
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(pd.DataFrame(columns=STANDARD_COLUMNS)),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )

    async def run():
        result = await advisor._handle_get_price_data(symbol="9999", period="3mo")
        assert "error" in result

    asyncio.run(run())


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
    import asyncio
    advisor = AIAdvisor(
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df(symbol="AAPL")),
        adapter=StubAdapter([{"text": "ok", "tool_calls": []}]),
    )
    async def run():
        result = await advisor._handle_get_price_data(symbol="aapl", period="3mo", market="us")
        assert result["symbol"] == "AAPL"
        assert result["data_count"] > 0

    asyncio.run(run())


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
        # 15-A-2: only read gemini_api_key; GOOGLE_API_KEY fallback removed
        has_key = bool(str(secrets.get("gemini_api_key", "")).strip())
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


# ---------------------------------------------------------------------------
# 15-A-2：google_api_key fallback 移除 regression
# ---------------------------------------------------------------------------


def test_resolve_api_key_gemini_no_longer_falls_back_to_google_api_key() -> None:
    """15-A-2 regression: _resolve_api_key('gemini') 不再讀 google_api_key。"""
    advisor_instance = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
    )
    # gemini_api_key 空白，只有 google_api_key
    secrets = {"google_api_key": "goog-fallback-should-not-work", "gemini_api_key": ""}
    key = advisor_instance._resolve_api_key("gemini", secrets)
    assert key == "", (
        "15-A-2: gemini should NOT fallback to google_api_key; got non-empty key"
    )


def test_resolve_api_key_gemini_reads_gemini_api_key() -> None:
    """gemini_api_key 有值時應正確回傳。"""
    advisor_instance = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
    )
    secrets = {"gemini_api_key": "AIza-gemini-real", "google_api_key": "goog-legacy"}
    key = advisor_instance._resolve_api_key("gemini", secrets)
    assert key == "AIza-gemini-real"


def test_gemini_provider_with_only_google_api_key_has_provider_error(monkeypatch, tmp_path) -> None:
    """Spec 15-A-2 line 5087 regression:
    advisor(provider=gemini) 在 .env 只有 GOOGLE_API_KEY 沒 GEMINI_API_KEY 時
    _provider_error 應為 'Missing API key for provider gemini.'
    """
    (tmp_path / "config.yaml").write_text(
        "ai:\n  enabled: true\n  provider: gemini\n  model: gemini-2.0-flash\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("", encoding="utf-8")
    monkeypatch.setattr(_config_module, "get_project_root", lambda: tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-should-not-work")
    _config_module.clear_config_cache()
    try:
        adv = AIAdvisor(storage=StubStorage(_make_daily_df()))
        assert adv._provider_error is not None, (
            "Expected _provider_error for gemini with only GOOGLE_API_KEY after 15-A-2 fallback removal"
        )
        assert "Missing API key" in adv._provider_error
    finally:
        _config_module.clear_config_cache()


# ---------------------------------------------------------------------------
# Phase 15-B: stream_chat & stream_complete tests
# ---------------------------------------------------------------------------


def test_stream_chat_disabled() -> None:
    import asyncio
    advisor = AIAdvisor(
        enabled=False,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
    )
    events = []

    async def run():
        async for event in advisor.stream_chat([]):
            events.append(event)

    asyncio.run(run())
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert "AI 功能已關閉" in events[0]["message"]


def test_stream_chat_missing_key() -> None:
    import asyncio
    with patch("src.ai.advisor.get_config", return_value={"ai": {"enabled": True, "provider": "openai"}, "secrets": {}}):
        advisor = AIAdvisor(storage=StubStorage(_make_daily_df()))
        assert advisor._provider_error is not None
        events = []

        async def run():
            async for event in advisor.stream_chat([]):
                events.append(event)

        asyncio.run(run())
        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert "Missing API key" in events[0]["message"]


def test_stream_chat_success() -> None:
    import asyncio
    class StubAsyncAdapter(BaseProviderAdapter):
        provider_name = "stub_async"

        async def complete(self, **kwargs) -> dict[str, Any]:
            return {}

        async def stream_complete(self, *, model, system_prompt, messages) -> AsyncIterator[str]:
            yield "Hi"
            yield " there"

        def normalize_tool_calls(self, raw_response) -> list:
            return []

    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAsyncAdapter(api_key="x", model="y"),
    )
    events = []

    async def run():
        async for event in advisor.stream_chat([]):
            events.append(event)

    asyncio.run(run())
    assert len(events) == 2
    assert events[0]["event"] == "token"
    assert events[0]["text"] == "Hi"
    assert events[1]["event"] == "token"
    assert events[1]["text"] == " there"


def test_stream_chat_exception_handling() -> None:
    import asyncio
    class FailedAsyncAdapter(BaseProviderAdapter):
        provider_name = "failed_async"

        async def complete(self, **kwargs) -> dict[str, Any]:
            return {}

        async def stream_complete(self, *, model, system_prompt, messages) -> AsyncIterator[str]:
            raise ValueError("Upstream timeout")
            yield ""

        def normalize_tool_calls(self, raw_response) -> list:
            return []

    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=FailedAsyncAdapter(api_key="x", model="y"),
    )
    events = []

    async def run():
        async for event in advisor.stream_chat([]):
            events.append(event)

    asyncio.run(run())
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert "Upstream timeout" in events[0]["message"]


# New Phase 15-B Tests to hit the gate requirement
# ---------------------------------------------------------------------------

def test_stream_chat_openai() -> None:
    import asyncio

    async def mock_stream_complete(*args, **kwargs):
        yield "He"
        yield "llo"

    with patch("src.ai.advisor.OpenAIAdapter.stream_complete", side_effect=mock_stream_complete):
        advisor = AIAdvisor(
            enabled=True,
            provider="openai",
            model="gpt-4o-mini",
            storage=StubStorage(_make_daily_df()),
            adapter=OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")
        )
        events = []

        async def run():
            async for event in advisor.stream_chat([]):
                events.append(event)

        asyncio.run(run())
        assert len(events) == 2
        assert events[0]["event"] == "token"
        assert events[0]["text"] == "He"
        assert events[1]["event"] == "token"
        assert events[1]["text"] == "llo"


def test_stream_chat_deepseek() -> None:
    import asyncio

    async def mock_stream_complete(*args, **kwargs):
        yield "Deep"
        yield "Seek"

    with patch("src.ai.advisor.DeepSeekAdapter.stream_complete", side_effect=mock_stream_complete):
        advisor = AIAdvisor(
            enabled=True,
            provider="deepseek",
            model="deepseek-v4-flash",
            storage=StubStorage(_make_daily_df()),
            adapter=DeepSeekAdapter(api_key="sk-ds-test", model="deepseek-v4-flash")
        )
        events = []

        async def run():
            async for event in advisor.stream_chat([]):
                events.append(event)

        asyncio.run(run())
        assert len(events) == 2
        assert events[0]["event"] == "token"
        assert events[0]["text"] == "Deep"
        assert events[1]["event"] == "token"
        assert events[1]["text"] == "Seek"


def test_stream_chat_anthropic_mock() -> None:
    import asyncio

    async def mock_stream_complete(*args, **kwargs):
        yield "Claude"
        yield " streams"

    with patch("src.ai.advisor.AnthropicAdapter.stream_complete", side_effect=mock_stream_complete):
        advisor = AIAdvisor(
            enabled=True,
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            storage=StubStorage(_make_daily_df()),
            adapter=AnthropicAdapter(api_key="sk-ant-test", model="claude-haiku-4-5-20251001")
        )
        events = []

        async def run():
            async for event in advisor.stream_chat([]):
                events.append(event)

        asyncio.run(run())
        assert len(events) == 2
        assert events[0]["event"] == "token"
        assert events[0]["text"] == "Claude"
        assert events[1]["event"] == "token"
        assert events[1]["text"] == " streams"


def test_stream_chat_gemini_mock() -> None:
    import asyncio

    async def mock_stream_complete(*args, **kwargs):
        yield "Gemini"
        yield " stream"

    with patch("src.ai.advisor.GeminiAdapter.stream_complete", side_effect=mock_stream_complete):
        advisor = AIAdvisor(
            enabled=True,
            provider="gemini",
            model="gemini-2.0-flash",
            storage=StubStorage(_make_daily_df()),
            adapter=GeminiAdapter(api_key="g-test", model="gemini-2.0-flash")
        )
        events = []

        async def run():
            async for event in advisor.stream_chat([]):
                events.append(event)

        asyncio.run(run())
        assert len(events) == 2
        assert events[0]["event"] == "token"
        assert events[0]["text"] == "Gemini"
        assert events[1]["event"] == "token"
        assert events[1]["text"] == " stream"


def test_adapters_stream_complete_parse_sse() -> None:
    import asyncio

    class AsyncIteratorWrapper:
        def __init__(self, items):
            self.items = items
            self.idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.idx < len(self.items):
                res = self.items[self.idx]
                self.idx += 1
                return res
            raise StopAsyncIteration

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = MagicMock(return_value=AsyncIteratorWrapper([
        "data: {\"choices\": [{\"delta\": {\"content\": \"He\"}}]}",
        "",
        "data: {\"choices\": [{\"delta\": {\"content\": \"llo\"}}]}",
        "data: [DONE]"
    ]))

    class MockStreamContext:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def stream(self, *args, **kwargs):
            return MockStreamContext()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient", return_value=MockClient()):
        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")

        async def run():
            chunks = []
            async for chunk in adapter.stream_complete(model="gpt-4o-mini", system_prompt="sys", messages=[]):
                chunks.append(chunk)
            return chunks

        res = asyncio.run(run())
        assert res == ["He", "llo"]


def test_stream_chat_with_tools_loop() -> None:
    import asyncio

    class StubAdapterWithTools:
        provider_name = "stub"
        def __init__(self):
            self.model = "stub-model"
            self.calls_count = 0

        async def stream_complete_with_tools(self, *, model, system_prompt, messages, tools):
            self.calls_count += 1
            if self.calls_count == 1:
                yield {"type": "token", "text": "Let me look up the RSI."}
                yield {"type": "tool_calls", "tool_calls": [{"id": "call-1", "name": "calculate_indicators", "arguments": {"symbol": "2330", "indicators": ["RSI_14"]}}]}
            elif self.calls_count == 2:
                yield {"type": "token", "text": "RSI is 68.5. That is close to overbought."}

    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=StubAdapterWithTools(),
    )

    events = []
    async def run():
        async for event in advisor.stream_chat([{"role": "user", "content": "What is 2330 RSI?"}]):
            events.append(event)

    asyncio.run(run())

    assert any(ev["event"] == "token" and ev["text"] == "Let me look up the RSI." for ev in events)
    assert any(ev["event"] == "tool_call" and ev["name"] == "calculate_indicators" for ev in events)
    assert any(ev["event"] == "tool_result" and ev["name"] == "calculate_indicators" and "RSI" in ev["output_summary"] for ev in events)
    assert any(ev["event"] == "token" and "RSI is 68.5" in ev["text"] for ev in events)


def test_stream_chat_max_rounds_exceeded() -> None:
    import asyncio

    class LoopAdapter:
        provider_name = "stub"
        def __init__(self):
            self.model = "stub-model"

        async def stream_complete_with_tools(self, *, model, system_prompt, messages, tools):
            # Always yields tool calls to force a loop
            yield {"type": "token", "text": "Continuous call"}
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": "loop-call",
                        "name": "calculate_indicators",
                        "arguments": {"symbol": "2330", "indicators": ["RSI_14"]},
                    }
                ],
            }

    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df()),
        adapter=LoopAdapter(),
    )

    events = []
    async def run():
        async for event in advisor.stream_chat([{"role": "user", "content": "Loop question"}], max_tool_rounds=6):
            events.append(event)

    asyncio.run(run())

    # Count the number of tool call events to ensure it stopped after exactly 6 rounds
    tool_calls = [ev for ev in events if ev["event"] == "tool_call"]
    assert len(tool_calls) == 6

    # Verify the error event was yielded at the very end
    error_events = [ev for ev in events if ev["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["message"] == "工具呼叫輪數過多，已停止。"


def test_openai_deepseek_delta_accumulator() -> None:
    import asyncio

    class AsyncIteratorWrapper:
        def __init__(self, items):
            self.items = items
            self.idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.idx < len(self.items):
                res = self.items[self.idx]
                self.idx += 1
                return res
            raise StopAsyncIteration

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = MagicMock(return_value=AsyncIteratorWrapper([
        "data: {\"choices\": [{\"delta\": {\"content\": \"Checking indicators\"}}]}",
        "data: {\"choices\": [{\"delta\": {\"tool_calls\": [{\"index\": 0, \"id\": \"call_abc\", \"function\": {\"name\": \"calculate_indicators\", \"arguments\": \"{\\\"sym\"}}]}}]}",
        "data: {\"choices\": [{\"delta\": {\"tool_calls\": [{\"index\": 0, \"function\": {\"arguments\": \"bol\\\": \\\"2330\\\"}\"}}]}}]}",
        "data: [DONE]"
    ]))

    class MockStreamContext:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def stream(self, *args, **kwargs):
            return MockStreamContext()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient", return_value=MockClient()):
        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")

        async def run():
            chunks = []
            async for chunk in adapter.stream_complete_with_tools(
                model="gpt-4o-mini",
                system_prompt="sys",
                messages=[],
                tools=[]
            ):
                chunks.append(chunk)
            return chunks

        res = asyncio.run(run())
        # The accumulator should merge the arguments string "{"sym" + "bol\": \"2330\"}" into {"symbol": "2330"}
        assert len(res) == 2
        assert res[0] == {"type": "token", "text": "Checking indicators"}
        assert res[1] == {
            "type": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_abc",
                    "name": "calculate_indicators",
                    "arguments": {"symbol": "2330"}
                }
            ]
        }


def test_anthropic_delta_accumulator() -> None:
    import asyncio

    @dataclass
    class ContentBlock:
        type: str
        id: str | None = None
        name: str | None = None

    @dataclass
    class ContentBlockStartEvent:
        type: str = "content_block_start"
        index: int = 0
        content_block: ContentBlock = None

    @dataclass
    class Delta:
        type: str
        text: str | None = None
        partial_json: str | None = None

    @dataclass
    class ContentBlockDeltaEvent:
        type: str = "content_block_delta"
        index: int = 0
        delta: Delta = None

    # Define mock stream
    class MockStream:
        def __init__(self, events):
            self.events = events
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.events:
                return self.events.pop(0)
            raise StopAsyncIteration

    mock_events = [
        ContentBlockStartEvent(index=0, content_block=ContentBlock(type="tool_use", id="call-anth", name="get_price_data")),
        ContentBlockDeltaEvent(index=0, delta=Delta(type="input_json_delta", partial_json="{\r\n  \"sym")),
        ContentBlockDeltaEvent(index=0, delta=Delta(type="input_json_delta", partial_json="bol\": \"2330\"\r\n}")),
    ]

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = MockStream(mock_events)

    adapter = AnthropicAdapter(api_key="sk-test", model="claude-3")
    adapter._async_client = mock_client

    async def run():
        chunks = []
        async for chunk in adapter.stream_complete_with_tools(
            model="claude-3",
            system_prompt="sys",
            messages=[],
            tools=[]
        ):
            chunks.append(chunk)
        return chunks

    res = asyncio.run(run())
    assert len(res) == 1
    assert res[0] == {
        "type": "tool_calls",
        "tool_calls": [
            {
                "id": "call-anth",
                "name": "get_price_data",
                "arguments": {"symbol": "2330"}
            }
        ]
    }


def test_gemini_accumulator() -> None:
    import asyncio

    class AsyncIteratorWrapper:
        def __init__(self, items):
            self.items = items
            self.idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.idx < len(self.items):
                res = self.items[self.idx]
                self.idx += 1
                return res
            raise StopAsyncIteration

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = MagicMock(return_value=AsyncIteratorWrapper([
        "data: {\"candidates\": [{\"content\": {\"parts\": [{\"text\": \"Checking Gemini...\"}]}}]}",
        "data: {\"candidates\": [{\"content\": {\"parts\": [{\"functionCall\": {\"name\": \"get_price_data\", \"args\": {\"symbol\": \"2330\"}}}]}}]}",
    ]))

    class MockStreamContext:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def stream(self, *args, **kwargs):
            return MockStreamContext()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient", return_value=MockClient()):
        adapter = GeminiAdapter(api_key="gem-test", model="gemini-1.5")

        async def run():
            chunks = []
            async for chunk in adapter.stream_complete_with_tools(
                model="gemini-1.5",
                system_prompt="sys",
                messages=[],
                tools=[]
            ):
                chunks.append(chunk)
            return chunks

        res = asyncio.run(run())
        assert len(res) == 2
        assert res[0] == {"type": "token", "text": "Checking Gemini..."}
        assert res[1] == {
            "type": "tool_calls",
            "tool_calls": [
                {
                    "id": "gemini-tool-1",
                    "name": "get_price_data",
                    "arguments": {"symbol": "2330"}
                }
            ]
        }


def test_ensure_daily_data_updated() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    acquire_mock = AsyncMock(return_value=True)
    release_mock = MagicMock()

    # 1. Mock lock busy scenario
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df("2330")),
        adapter=StubAdapter([]),
    )

    async def run_lock_busy():
        with patch("api.job_manager.JobManager.is_write_locked", return_value=True):
            # Case A: Had local data -> use local data and return a warning
            res = await advisor._ensure_daily_data_updated("2330", "tw", None)
            assert res["warning"] == "資料更新正在進行中，暫用本機資料"
            assert not res["df"].empty
            assert res["error"] is None

            # Case B: No local data -> return a busy error
            advisor_no_data = AIAdvisor(
                enabled=True,
                provider="anthropic",
                model="stub",
                storage=StubStorage(pd.DataFrame()),
                adapter=StubAdapter([]),
            )
            res_no_data = await advisor_no_data._ensure_daily_data_updated("2330", "tw", None)
            assert res_no_data["error"] == "資料更新正在進行中，稍後再試"
            assert res_no_data["df"].empty

    asyncio.run(run_lock_busy())

    # 2. Mock update fails scenario
    advisor_fail = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df("2330")),
        adapter=StubAdapter([]),
    )

    async def run_update_fails():
        with patch("api.job_manager.JobManager.acquire_write_lock", acquire_mock), \
             patch("api.job_manager.JobManager.release_write_lock", release_mock), \
             patch("src.services.data_service.run_maintenance", side_effect=RuntimeError("Source down")):
            # Case A: Had local data -> use local data and return a warning
            res = await advisor_fail._ensure_daily_data_updated("2330", "tw", None)
            assert "更新失敗，改用本機既有資料" in res["warning"]
            assert not res["df"].empty
            assert res["error"] is None

            # Case B: No local data -> return a structured error
            advisor_fail_no_data = AIAdvisor(
                enabled=True,
                provider="anthropic",
                model="stub",
                storage=StubStorage(pd.DataFrame()),
                adapter=StubAdapter([]),
            )
            # B1: FinMind token missing
            with patch("src.core.config.get_config", return_value={"secrets": {"finmind_token": ""}}):
                res_no_token = await advisor_fail_no_data._ensure_daily_data_updated("2330", "tw", None)
                assert "FinMind token missing" in res_no_token["error"]

            # B2: Data source unavailable
            with patch("src.core.config.get_config", return_value={"secrets": {"finmind_token": "token-xyz"}}):
                res_no_source = await advisor_fail_no_data._ensure_daily_data_updated("2330", "tw", None)
                assert "data source unavailable" in res_no_source["error"]

    asyncio.run(run_update_fails())

    # 3. Mock already updated scenario
    advisor_updated = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorage(_make_daily_df("2330")),
        adapter=StubAdapter([]),
    )

    async def run_already_updated():
        updated_set = {("2330", "tw")}
        res_updated = await advisor_updated._ensure_daily_data_updated("2330", "tw", updated_set)
        assert res_updated["warning"] is None
        assert res_updated["error"] is None
        assert not res_updated["df"].empty

    asyncio.run(run_already_updated())


# ---------------------------------------------------------------------------
# Phase 15-E: AI Q&A investment return tool (calculate_total_return) tests
# ---------------------------------------------------------------------------


class StubStorageWithDividends:
    def __init__(self, daily_df, dividends_df=None):
        self.daily = daily_df
        if dividends_df is None:
            # Provide a dummy row outside the calculation range to ensure had_local_data is True
            # while not affecting calculation results.
            self.dividends = pd.DataFrame({
                "date": [pd.to_datetime("2000-01-01")],
                "cash_dividend": [0.0],
                "stock_dividend": [0.0],
                "symbol": ["2330"]
            })
        else:
            self.dividends = dividends_df

    def load_daily(self, symbol: str, market: str = "tw") -> pd.DataFrame:
        if self.daily.empty:
            return self.daily.copy()
        return self.daily[self.daily["symbol"] == symbol].copy()

    def load_minute(self, symbol: str, market: str = "tw") -> pd.DataFrame:
        return pd.DataFrame()

    def load_dividends(self, symbol: str, market: str = "tw") -> pd.DataFrame:
        if self.dividends.empty:
            return self.dividends.copy()
        df = self.dividends.copy()
        if len(df) == 1 and df.iloc[0]["date"] == pd.to_datetime("2000-01-01"):
            df["symbol"] = symbol
            return df
        return df[df["symbol"] == symbol].copy()

    def save_dividends(self, symbol: str, df: pd.DataFrame, market: str = "tw") -> None:
        pass


def _make_dividends_df(symbol: str = "2330") -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-03-21", "2025-06-20"]),
        "cash_dividend": [1.40, 1.10],
        "stock_dividend": [0.0, 0.0],
        "symbol": [symbol, symbol]
    })


def test_calculate_total_return_single_symbol() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=200)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-03-31",
            initial_amount=100000.0,
            market="tw",
            buy_price_basis="open",
            dividend_mode="cash",
        )
        assert not res["errors"]
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["symbol"] == "2330"
        assert ret["buy_price"] == 101.0
        assert ret["end_price"] == 189.5
        assert ret["shares"] == round(100000.0 / 101.0, 6)
        assert ret["cash_dividend_per_share"] == 1.40
        assert len(ret["dividends"]) == 1
        assert ret["dividends"][0]["date"] == "2025-03-21"
        assert ret["total_return_pct"] > 0
        assert ret["holding_days"] > 0
        assert ret["annualized_return_pct"] is not None

    asyncio.run(run())


def test_calculate_total_return_multi_symbol_order() -> None:
    import asyncio
    daily_df = pd.concat([_make_daily_df("2330", periods=100), _make_daily_df("0050", periods=100)])
    dividends_df = pd.concat([_make_dividends_df("2330"), _make_dividends_df("0050")])
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["0050", "2330"],
            start_date="2025-01-02",
            end_date="2025-02-15",
            initial_amount=100000.0,
            market="tw",
            buy_price_basis="open",
            dividend_mode="cash",
        )
        assert not res["errors"]
        assert len(res["results"]) == 2
        assert res["results"][0]["symbol"] == "0050"
        assert res["results"][1]["symbol"] == "2330"

    asyncio.run(run())


def test_calculate_total_return_start_non_trading_day_aligns_next() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    daily_df = daily_df[daily_df["date"].dt.dayofweek < 5].copy()
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-04",
            end_date="2025-01-20",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["buy_date"] == "2025-01-06"
        assert any("起始日" in w and "非交易日" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_end_non_trading_day_aligns_previous() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    daily_df = daily_df[daily_df["date"].dt.dayofweek < 5].copy()
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-19",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["end_trade_date"] == "2025-01-17"
        assert any("非交易日" in w and "結束日" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_start_before_first_data_within_30_days_warns() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2024-12-15",
            end_date="2025-01-15",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["buy_date"] == "2025-01-01"
        assert any("早於本機最早資料日" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_start_before_first_data_over_30_days_errors() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2024-11-01",
            end_date="2025-01-15",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["errors"]) == 1
        assert "早於本機最早資料超過 30 天" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_end_after_latest_data_warns() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=10)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-02-01",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["end_trade_date"] == "2025-01-10"
        assert any("晚於本機最新資料日" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_same_trade_date_warns_no_annualized() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-02",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert ret["holding_days"] == 0
        assert ret["annualized_return_pct"] is None
        assert any("同一交易日" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_dividend_range_excludes_buy_date() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-05"]),
        "cash_dividend": [1.50, 1.00],
        "stock_dividend": [0.0, 0.0],
        "symbol": ["2330", "2330"]
    })
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        ret = res["results"][0]
        assert len(ret["dividends"]) == 1
        assert ret["dividends"][0]["date"] == "2025-01-05"
        assert ret["cash_dividend_per_share"] == 1.00

    asyncio.run(run())


def test_calculate_total_return_dividend_date_is_ex_dividend_date() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-05"]),
        "cash_dividend": [2.00],
        "stock_dividend": [0.0],
        "symbol": ["2330"]
    })
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
        )
        ret = res["results"][0]
        assert ret["dividends"][0]["date"] == "2025-01-05"

    asyncio.run(run())


def test_calculate_total_return_stock_dividend_warns_not_counted() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-05"]),
        "cash_dividend": [1.50],
        "stock_dividend": [0.1],
        "symbol": ["2330"]
    })
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
        )
        ret = res["results"][0]
        assert any("股票股利" in w for w in ret["warnings"])
        assert ret["stock_dividend_per_share"] == 0.10
        assert ret["dividends"][0]["stock_dividend"] == 0.10

    asyncio.run(run())


def test_calculate_total_return_missing_daily_errors_one_symbol_only() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330", "9999"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
        )
        assert len(res["results"]) == 1
        assert res["results"][0]["symbol"] == "2330"
        assert len(res["errors"]) == 1
        assert res["errors"][0]["symbol"] == "9999"

    asyncio.run(run())


def test_calculate_total_return_refreshes_dividends_when_needed() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": None, "error": None}) as mock_refresh:
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert not res["errors"]
            mock_refresh.assert_called_once()

    asyncio.run(run())


def test_calculate_total_return_dividends_refreshed_source() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": None, "error": None}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert res["results"][0]["dividends_source"] == "refreshed"

    asyncio.run(run())


def test_calculate_total_return_dividends_local_fallback_on_refresh_fail() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": "Failed connection", "error": "Connection Timeout"}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert not res["errors"]
            ret = res["results"][0]
            assert ret["dividends_source"] == "local_fallback"
            assert any("股利更新失敗" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_dividends_missing_after_refresh_fail_errors() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, pd.DataFrame()),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": None, "error": "Fetch Error"}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert len(res["errors"]) == 1
            assert "無股利資料" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_dividend_lock_busy_with_local_fallback() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": "資料更新正在進行中，暫用本機資料", "error": "Lock Busy"}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert len(res["results"]) == 1
            ret = res["results"][0]
            assert ret["dividends_source"] == "local_fallback"
            assert any("股利更新失敗" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_dividend_lock_busy_without_local_errors() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, pd.DataFrame()),
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": "資料更新正在進行中", "error": "Lock Busy"}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert len(res["errors"]) == 1
            assert "無股利資料" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_dividends_refresh_once_per_chat() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        updated_set = set()
        with patch.object(advisor, "_ensure_dividends_updated", wraps=advisor._ensure_dividends_updated) as mock_ref:
            await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
                updated_dividend_symbols=updated_set,
            )
            await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
                updated_dividend_symbols=updated_set,
            )
            assert mock_ref.call_count == 2
            assert ("2330", "tw") in updated_set

    asyncio.run(run())


def test_calculate_total_return_market_us_rejected() -> None:
    import asyncio
    daily_df = _make_daily_df("AAPL", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["AAPL"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="us",
        )
        assert len(res["errors"]) == 1
        assert "僅支援台股" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_unsupported_dividend_mode_rejected() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
            dividend_mode="reinvest",
        )
        assert len(res["errors"]) == 1
        assert "僅支援現金股利持有" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_unsupported_buy_price_basis_rejected() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-01-10",
            initial_amount=100000.0,
            market="tw",
            buy_price_basis="high",
        )
        assert len(res["errors"]) == 1
        assert "buy_price_basis 僅支援" in res["errors"][0]["error"]

    asyncio.run(run())


def test_calculate_total_return_rounding_rules() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2025-03-31",
            initial_amount=100000.0,
            market="tw",
        )
        ret = res["results"][0]
        assert str(ret["buy_price"]).endswith(".0") or len(str(ret["buy_price"]).split(".")[1]) <= 2
        assert str(ret["end_price"]).endswith(".0") or len(str(ret["end_price"]).split(".")[1]) <= 2
        assert len(str(ret["shares"]).split(".")[1]) <= 6
        assert len(str(ret["cash_dividend_per_share"]).split(".")[1]) <= 4
        assert len(str(ret["dividend_cash"]).split(".")[1]) <= 2
        assert len(str(ret["market_value"]).split(".")[1]) <= 2
        assert len(str(ret["final_value"]).split(".")[1]) <= 2
        assert len(str(ret["total_return_pct"]).split(".")[1]) <= 2

    asyncio.run(run())


def test_calculate_total_return_holding_days_and_annualized() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=400)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapter([]),
    )

    async def run():
        res = await advisor._handle_calculate_total_return(
            symbols=["2330"],
            start_date="2025-01-02",
            end_date="2026-02-15",
            initial_amount=100000.0,
            market="tw",
        )
        ret = res["results"][0]
        assert ret["holding_days"] > 365
        assert ret["annualized_return_pct"] is not None
        assert not any("持有期間不足一年" in w for w in ret["warnings"])

    asyncio.run(run())


def test_calculate_total_return_triggers_daily_update_once() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df),
        adapter=StubAdapter([]),
    )

    async def run():
        updated_set = set()
        with patch.object(advisor, "_ensure_daily_data_updated", wraps=advisor._ensure_daily_data_updated) as mock_ref:
            await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
                updated_daily_symbols=updated_set,
            )
            mock_ref.assert_called_once()
            assert ("2330", "tw") in updated_set

    asyncio.run(run())


def test_stream_chat_can_use_calculate_total_return_tool() -> None:
    import asyncio

    class StubAdapterWithReturnTool:
        provider_name = "stub"
        def __init__(self):
            self.model = "stub-model"
            self.calls_count = 0

        async def stream_complete_with_tools(self, *, model, system_prompt, messages, tools):
            self.calls_count += 1
            if self.calls_count == 1:
                yield {"type": "token", "text": "Let me calculate the total return."}
                yield {
                    "type": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "ret-call-1",
                            "name": "calculate_total_return",
                            "arguments": {
                                "symbols": ["2330"],
                                "start_date": "2025-01-02",
                                "end_date": "2025-03-31",
                                "initial_amount": 100000.0,
                                "market": "tw",
                            }
                        }
                    ]
                }
            elif self.calls_count == 2:
                yield {"type": "token", "text": "The total return for 2330 is 14.01%."}

    daily_df = _make_daily_df("2330", periods=100)
    dividends_df = _make_dividends_df("2330")
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, dividends_df),
        adapter=StubAdapterWithReturnTool(),
    )

    events = []
    async def run():
        async for event in advisor.stream_chat([{"role": "user", "content": "How much is my return on 2330?"}]):
            events.append(event)

    asyncio.run(run())

    assert any(ev["event"] == "token" and ev["text"] == "Let me calculate the total return." for ev in events)
    assert any(ev["event"] == "tool_call" and ev["name"] == "calculate_total_return" for ev in events)
    assert any(ev["event"] == "tool_result" and ev["name"] == "calculate_total_return" and "報酬" in ev["output_summary"] for ev in events)
    assert any(ev["event"] == "token" and "14.01%" in ev["text"] for ev in events)


def test_calculate_total_return_dividends_empty_after_successful_refresh_errors() -> None:
    import asyncio
    daily_df = _make_daily_df("2330", periods=50)
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub",
        storage=StubStorageWithDividends(daily_df, pd.DataFrame()),  # explicitly empty local dividends
        adapter=StubAdapter([]),
    )

    async def run():
        with patch.object(advisor, "_ensure_dividends_updated", return_value={"warning": None, "error": None}):
            res = await advisor._handle_calculate_total_return(
                symbols=["2330"],
                start_date="2025-01-02",
                end_date="2025-01-10",
                initial_amount=100000.0,
                market="tw",
            )
            assert len(res["errors"]) == 1
            assert "無股利資料，無法計算含息報酬" in res["errors"][0]["error"]

    asyncio.run(run())



