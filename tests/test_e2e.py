from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from src.ai.advisor import AIAdvisor
from src.backtest.engine_vec import VectorizedBacktester
from src.backtest.report import TearsheetReport
from src.core.config import clear_config_cache, get_config
from src.data.storage import ParquetStorage
from src.strategy.examples.ma_cross import MACrossStrategy


class _ReplayToolAdapter:
    """Deterministic adapter for exercising advisor tool-call loop in tests."""

    model = "stub-model"

    def __init__(self) -> None:
        self._round = 0

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _ = (model, system_prompt, tools)
        self._round += 1

        if self._round == 1:
            return {
                "text": "",
                "tool_calls": [
                    {
                        "id": "invalid-symbol-call",
                        "name": "get_price_data",
                        "arguments": {"symbol": "9999", "period": "3mo"},
                    }
                ],
            }

        tool_messages = [message for message in messages if message.get("role") == "tool"]
        if not tool_messages:
            return {"text": "未收到工具輸出。", "tool_calls": []}

        latest_tool_content = str(tool_messages[-1].get("content", ""))
        try:
            payload = json.loads(latest_tool_content)
        except json.JSONDecodeError:
            payload = {"error": latest_tool_content}

        if isinstance(payload, dict) and payload.get("error"):
            return {"text": f"查詢失敗：{payload['error']}", "tool_calls": []}
        return {"text": "查詢成功。", "tool_calls": []}


def _has_provider_api_key(provider: str, secrets: dict[str, Any]) -> bool:
    if provider == "anthropic":
        return bool(str(secrets.get("anthropic_api_key", "")).strip())
    if provider == "openai":
        return bool(str(secrets.get("openai_api_key", "")).strip())
    if provider == "gemini":
        # 15-A-2: only read gemini_api_key; GOOGLE_API_KEY fallback removed
        return bool(str(secrets.get("gemini_api_key", "")).strip())
    return False


@pytest.mark.integration
def test_full_backtest_pipeline() -> None:
    storage = ParquetStorage()
    df = storage.load_daily("2330")
    if df.empty:
        pytest.skip("No local daily data for symbol 2330.")

    config = get_config()
    backtest_cfg = config.get("backtest", {}) if isinstance(config, dict) else {}
    initial_capital = float(backtest_cfg.get("initial_capital", 1_000_000))

    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    result = VectorizedBacktester(initial_capital=initial_capital).run(strategy=strategy, data=df)

    assert not result.equity_curve.empty

    out_file = Path("data/backtest/e2e_tearsheet_integration.html")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    TearsheetReport(result).save_html(str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0


@pytest.mark.integration
def test_ai_advisor_real_question() -> None:
    clear_config_cache()
    config = get_config()
    ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
    secrets = config.get("secrets", {}) if isinstance(config, dict) else {}

    if not bool(ai_section.get("enabled", True)):
        pytest.skip("AI is disabled in config (ai.enabled=false).")

    provider = str(ai_section.get("provider", "anthropic")).strip().lower()
    if not _has_provider_api_key(provider, secrets if isinstance(secrets, dict) else {}):
        pytest.skip(f"{provider} API key is not configured.")

    storage = ParquetStorage()
    if storage.load_daily("2330").empty:
        pytest.skip("No local daily data for symbol 2330.")

    advisor = AIAdvisor(storage=storage)
    start = time.perf_counter()
    answer = advisor.ask("2330 的 RSI 是多少？")
    elapsed = time.perf_counter() - start

    if answer.startswith("AI provider request failed:"):
        pytest.skip(answer)

    assert elapsed < 30.0
    assert "免責聲明" in answer
    assert re.search(r"\d", answer) is not None


@pytest.mark.integration
def test_invalid_symbol_graceful() -> None:
    advisor = AIAdvisor(
        enabled=True,
        provider="anthropic",
        model="stub-model",
        storage=ParquetStorage(),
        adapter=_ReplayToolAdapter(),
    )

    answer = advisor.ask("9999 的 RSI 怎麼看？")

    assert isinstance(answer, str)
    assert "免責聲明" in answer
    assert ("error" in answer.lower()) or ("失敗" in answer) or ("找不到" in answer)
