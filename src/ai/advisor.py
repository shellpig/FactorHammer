"""Provider-neutral AI advisor with tool-calling support."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from src.core.config import get_config
from src.core.exceptions import AICallError, AIDisabledError
from src.core.market import get_market_spec, normalize_market, normalize_symbol
from src.data.storage import ParquetStorage

SYSTEM_PROMPT = """你是一個台股技術分析助理。你的工作是：
1. 根據使用者提供的工具數據，客觀描述技術指標的現況
2. 解釋技術術語的含義
3. 說明常見的技術型態與歷史統計意義

你不應該：
- 明確建議使用者買進或賣出
- 預測股價未來走勢
- 給予資金配置建議
"""

DISCLAIMER = """⚠️ 免責聲明：以上分析僅為技術指標數值的客觀陳述，不構成任何投資建議。
技術分析基於歷史數據，不保證未來走勢。AI 無法預測市場，所有投資決策
請自行判斷，並以券商官方行情為準。投資一定有風險，過去績效不代表未來報酬。"""

DASHBOARD_SYSTEM_PROMPT = """你是個股儀表板的分析助理。
請依使用者提供的結構化資料，輸出 JSON 物件（不要額外文字），欄位如下：
{
  "industry_overview": ["...", "...", "..."],
  "company_overview": ["...", "...", "..."],
  "volume_price_analysis": "...",
  "scenarios": [
    {"name": "...", "entry_range": "...", "stop_loss": 0.0, "target": "..."},
    {"name": "...", "entry_range": "...", "stop_loss": 0.0, "target": "..."},
    {"name": "...", "entry_range": "...", "stop_loss": 0.0, "target": "..."}
  ],
  "conclusion": "..."
}

規則：
1) 不得編造未提供的數字。
2) 劇本價位需基於提供的支撐/壓力區間。
3) 語氣為研究情境推演，不得出現保證獲利、必買等語句。
4) 使用繁體中文。"""

_TRADITIONAL_CHINESE_REQUIREMENT = "You must reply entirely in Traditional Chinese (zh-TW)."

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_price_data",
        "description": "取得指定股票的歷史 K 線資料（日K 或分K）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "台股代碼，如 '2330'"},
                "period": {"type": "string", "description": "時間範圍，如 '3mo'、'6mo'、'1y'"},
                "freq": {
                    "type": "string",
                    "enum": ["daily", "60min", "30min", "5min"],
                    "description": "K 線頻率，預設 daily",
                },
            },
            "required": ["symbol", "period"],
        },
    },
    {
        "name": "calculate_indicators",
        "description": "計算技術指標（支援：RSI_14, MACD, MA_5, MA_20, MA_60）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "台股代碼"},
                "indicators": {"type": "array", "items": {"type": "string"}, "description": "指標列表"},
                "period": {"type": "string", "description": "計算期間，預設 '6mo'"},
            },
            "required": ["symbol", "indicators"],
        },
    },
    {
        "name": "get_support_resistance",
        "description": "計算近期支撐與壓力位（基於近期高低點與均線）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "台股代碼"},
                "lookback": {"type": "integer", "description": "回溯交易日數，預設 60"},
            },
            "required": ["symbol"],
        },
    },
]

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "deepseek": "deepseek-v4-flash",
}

SUPPORTED_FREQS = {"daily", "60min", "30min", "5min"}
_PERIOD_TO_ROWS = {
    "1mo": 22,
    "3mo": 66,
    "6mo": 132,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}


@dataclass(slots=True)
class NormalizedToolCall:
    """Provider-agnostic normalized tool call."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class TradingScenario:
    """Trading scenario for dashboard analysis."""

    name: str
    entry_range: str
    stop_loss: float
    target: str


@dataclass(slots=True)
class DashboardAnalysis:
    """Structured dashboard analysis output."""

    industry_overview: list[str]
    company_overview: list[str]
    volume_price_analysis: str
    scenarios: list[TradingScenario]
    conclusion: str


class BaseProviderAdapter(ABC):
    """Common provider adapter interface."""

    provider_name: str

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @abstractmethod
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
        """Return provider response with shape: {text: str, tool_calls: list[dict]}."""

    @abstractmethod
    def normalize_tool_calls(self, raw_response: Any) -> list[NormalizedToolCall]:
        """Normalize provider-specific tool call payloads."""

    @staticmethod
    def _json_loads_maybe(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return loaded if isinstance(loaded, dict) else {}
        return {}


class AnthropicAdapter(BaseProviderAdapter):
    """Anthropic messages API adapter."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0):
        super().__init__(api_key=api_key, model=model, timeout_seconds=timeout_seconds)
        from anthropic import Anthropic  # Imported lazily to keep optionality in tests.

        self._client = Anthropic(api_key=api_key)

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
        response = self._client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=self._to_anthropic_messages(messages),
        )
        return {
            "text": self._extract_text(response),
            "tool_calls": [tc.__dict__ for tc in self.normalize_tool_calls(response)],
        }

    def normalize_tool_calls(self, raw_response: Any) -> list[NormalizedToolCall]:
        content = getattr(raw_response, "content", None)
        if content is None and isinstance(raw_response, dict):
            content = raw_response.get("content", [])
        if content is None:
            return []

        calls: list[NormalizedToolCall] = []
        for idx, block in enumerate(content, start=1):
            block_type = getattr(block, "type", None)
            if block_type is None and isinstance(block, dict):
                block_type = block.get("type")
            if block_type != "tool_use":
                continue

            tool_id = getattr(block, "id", None)
            name = getattr(block, "name", None)
            arguments = getattr(block, "input", None)
            if isinstance(block, dict):
                tool_id = block.get("id", tool_id)
                name = block.get("name", name)
                arguments = block.get("input", arguments)

            calls.append(
                NormalizedToolCall(
                    id=str(tool_id or f"anthropic-tool-{idx}"),
                    name=str(name or ""),
                    arguments=self._json_loads_maybe(arguments),
                )
            )
        return calls

    def _to_anthropic_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role in {"user", "assistant"}:
                if role == "assistant" and message.get("tool_calls"):
                    blocks: list[dict[str, Any]] = []
                    text = str(message.get("content", "")).strip()
                    if text:
                        blocks.append({"type": "text", "text": text})

                    for tool_call in message.get("tool_calls", []):
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_call.get("id"),
                                "name": tool_call.get("name"),
                                "input": tool_call.get("arguments", {}),
                            }
                        )
                    out.append({"role": "assistant", "content": blocks})
                else:
                    out.append({"role": role, "content": str(message.get("content", ""))})
            elif role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.get("tool_call_id"),
                                "content": str(message.get("content", "")),
                            }
                        ],
                    }
                )
        return out

    def _extract_text(self, response: Any) -> str:
        content = getattr(response, "content", None)
        if content is None:
            return ""

        text_blocks: list[str] = []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_blocks.append(str(getattr(block, "text", "")).strip())
            elif isinstance(block, dict) and block.get("type") == "text":
                text_blocks.append(str(block.get("text", "")).strip())
        return "\n".join(part for part in text_blocks if part)


class OpenAIAdapter(BaseProviderAdapter):
    """OpenAI Chat Completions adapter."""

    provider_name = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0, base_url: str | None = None):
        super().__init__(api_key=api_key, model=model, timeout_seconds=timeout_seconds)
        self._base_url = base_url or self.DEFAULT_BASE_URL

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
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages, system_prompt),
            "tools": self._to_openai_tools(tools),
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if thinking is not None:
            payload["thinking"] = thinking
        response = requests.post(
            self._base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI API error: {response.status_code} {response.text[:300]}")

        body = response.json()
        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        return {
            "text": str(message.get("content") or ""),
            "tool_calls": [tc.__dict__ for tc in self.normalize_tool_calls(body)],
        }

    def normalize_tool_calls(self, raw_response: Any) -> list[NormalizedToolCall]:
        message: dict[str, Any] = {}
        if isinstance(raw_response, dict) and "choices" in raw_response:
            choices = raw_response.get("choices", [])
            if choices:
                message = choices[0].get("message", {}) or {}
        elif isinstance(raw_response, dict):
            message = raw_response

        raw_calls = message.get("tool_calls", []) or []
        out: list[NormalizedToolCall] = []
        for idx, call in enumerate(raw_calls, start=1):
            fn = call.get("function", {}) if isinstance(call, dict) else {}
            out.append(
                NormalizedToolCall(
                    id=str((call or {}).get("id") or f"openai-tool-{idx}"),
                    name=str(fn.get("name", "")),
                    arguments=self._json_loads_maybe(fn.get("arguments", {})),
                )
            )
        return out

    def _to_openai_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]

    def _to_openai_messages(self, messages: list[dict[str, Any]], system_prompt: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for message in messages:
            role = message.get("role")
            if role in {"user", "assistant"}:
                if role == "assistant" and message.get("tool_calls"):
                    openai_tool_calls = []
                    for tool_call in message["tool_calls"]:
                        openai_tool_calls.append(
                            {
                                "id": tool_call.get("id"),
                                "type": "function",
                                "function": {
                                    "name": tool_call.get("name"),
                                    "arguments": json.dumps(tool_call.get("arguments", {}), ensure_ascii=False),
                                },
                            }
                        )
                    out.append(
                        {
                            "role": "assistant",
                            "content": message.get("content"),
                            "tool_calls": openai_tool_calls,
                        }
                    )
                else:
                    out.append({"role": role, "content": str(message.get("content", ""))})
            elif role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.get("tool_call_id"),
                        "name": message.get("name"),
                        "content": str(message.get("content", "")),
                    }
                )
        return out


class GeminiAdapter(BaseProviderAdapter):
    """Google Gemini generateContent adapter."""

    provider_name = "gemini"

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
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": self._to_gemini_contents(messages),
            "tools": [{"functionDeclarations": self._to_gemini_functions(tools)}],
        }
        response = requests.post(
            endpoint,
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Gemini API error: {response.status_code} {response.text[:300]}")

        body = response.json()
        return {
            "text": self._extract_text(body),
            "tool_calls": [tc.__dict__ for tc in self.normalize_tool_calls(body)],
        }

    def normalize_tool_calls(self, raw_response: Any) -> list[NormalizedToolCall]:
        if not isinstance(raw_response, dict):
            return []

        candidates = raw_response.get("candidates", []) or []
        if not candidates:
            return []

        parts = candidates[0].get("content", {}).get("parts", []) or []
        out: list[NormalizedToolCall] = []
        for idx, part in enumerate(parts, start=1):
            fn_call = part.get("functionCall") if isinstance(part, dict) else None
            if not isinstance(fn_call, dict):
                continue

            out.append(
                NormalizedToolCall(
                    id=str(fn_call.get("id") or f"gemini-tool-{idx}"),
                    name=str(fn_call.get("name", "")),
                    arguments=self._json_loads_maybe(fn_call.get("args", {})),
                )
            )
        return out

    def _extract_text(self, body: dict[str, Any]) -> str:
        candidates = body.get("candidates", []) or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", []) or []
        text_parts = [str(part.get("text", "")).strip() for part in parts if isinstance(part, dict) and part.get("text")]
        return "\n".join(part for part in text_parts if part)

    def _to_gemini_functions(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
            for tool in tools
        ]

    def _to_gemini_contents(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "user":
                out.append({"role": "user", "parts": [{"text": str(message.get("content", ""))}]})
            elif role == "assistant":
                parts: list[dict[str, Any]] = []
                text = str(message.get("content", "")).strip()
                if text:
                    parts.append({"text": text})
                for tool_call in message.get("tool_calls", []):
                    parts.append(
                        {
                            "functionCall": {
                                "id": tool_call.get("id"),
                                "name": tool_call.get("name"),
                                "args": tool_call.get("arguments", {}),
                            }
                        }
                    )
                out.append({"role": "model", "parts": parts or [{"text": ""}]})
            elif role == "tool":
                out.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": message.get("name"),
                                    "response": {"content": str(message.get("content", ""))},
                                }
                            }
                        ],
                    }
                )
        return out


class DeepSeekAdapter(OpenAIAdapter):
    """DeepSeek adapter — OpenAI-compatible endpoint at deepseek.com."""

    provider_name = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"


PROVIDER_ADAPTERS: dict[str, type[BaseProviderAdapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
    "deepseek": DeepSeekAdapter,
}


class AIAdvisor:
    """Provider-neutral LLM advisor for technical-analysis Q&A."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
        storage: ParquetStorage | None = None,
        adapter: BaseProviderAdapter | None = None,
    ):
        config = get_config()
        ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
        secrets = config.get("secrets", {}) if isinstance(config, dict) else {}
        self.enabled = self._as_bool(enabled if enabled is not None else ai_section.get("enabled", True))
        ai_provider = str(provider or ai_section.get("provider", "anthropic")).strip().lower()

        if ai_provider not in PROVIDER_ADAPTERS:
            raise ValueError(f"Unsupported AI provider: {ai_provider}")

        self.provider = ai_provider
        self.model = str(model or ai_section.get("model") or DEFAULT_MODELS[self.provider])
        self.storage = storage or ParquetStorage()
        self.provider_adapter: BaseProviderAdapter | None = adapter
        self._provider_error: str | None = None

        if not self.enabled:
            self.provider_adapter = None
            return

        if self.provider_adapter is None:
            api_key = self._resolve_api_key(self.provider, secrets)
            if not api_key:
                self._provider_error = f"Missing API key for provider '{self.provider}'."
            else:
                adapter_cls = PROVIDER_ADAPTERS[self.provider]
                self.provider_adapter = adapter_cls(api_key=api_key, model=self.model)

    def ask(self, question: str, max_tool_rounds: int = 6) -> str:
        """Ask the assistant and always append disclaimer to final text."""
        if not self.enabled:
            return "AI 功能已關閉（ai.enabled=false）。"

        question_text = str(question).strip()
        if not question_text:
            return self._append_disclaimer("請先輸入問題。")

        if self._provider_error:
            return self._append_disclaimer(f"AI provider configuration error: {self._provider_error}")

        if self.provider_adapter is None:
            return self._append_disclaimer("AI provider adapter is not initialized.")

        messages: list[dict[str, Any]] = [{"role": "user", "content": question_text}]

        for _ in range(max_tool_rounds):
            try:
                response = self.provider_adapter.complete(
                    model=self.model,
                    system_prompt=SYSTEM_PROMPT,
                    messages=messages,
                    tools=TOOLS,
                )
            except Exception as exc:  # noqa: BLE001
                return self._append_disclaimer(f"AI provider request failed: {exc}")

            tool_calls = list(response.get("tool_calls", []))
            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": str(response.get("text", "")),
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    tool_name = str(tool_call.get("name", ""))
                    tool_id = str(tool_call.get("id", "tool-call"))
                    tool_input = tool_call.get("arguments", {}) or {}
                    tool_output = self._execute_tool(tool_name, tool_input)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": json.dumps(tool_output, ensure_ascii=False, default=str),
                        }
                    )
                continue

            return self._append_disclaimer(str(response.get("text", "")))

        return self._append_disclaimer("工具呼叫輪數過多，已停止。")

    def generate_stock_dashboard_analysis(
        self,
        symbol: str,
        technical_summary: Any,
        chip_summary: Any | None,
        company_info: dict[str, Any] | None,
        recent_prices: pd.DataFrame,
        market: str = "tw",
        currency: str | None = None,
    ) -> DashboardAnalysis:
        """Generate dashboard analysis with structured JSON output."""
        if not self.enabled:
            raise AIDisabledError("AI 功能未啟用（ai.enabled=false）。")
        if self._provider_error:
            raise AICallError(self._provider_error)
        if self.provider_adapter is None:
            raise AICallError("AI provider adapter is not initialized.")
        normalized_market = normalize_market(market)
        try:
            normalized_symbol = normalize_symbol(symbol, market=normalized_market)
        except ValueError as exc:
            raise AICallError(f"Invalid symbol for market={normalized_market}: {symbol}") from exc
        resolved_currency = str(currency or get_market_spec(normalized_market).currency)

        payload = self._build_dashboard_payload(
            symbol=normalized_symbol,
            technical_summary=technical_summary,
            chip_summary=chip_summary,
            company_info=company_info,
            recent_prices=recent_prices,
            market=normalized_market,
            currency=resolved_currency,
        )
        user_prompt = (
            "請依下列資料輸出 JSON。\n"
            "注意 scenarios 必須恰好 3 個。\n"
            f"DATA:\n{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            f"{_TRADITIONAL_CHINESE_REQUIREMENT}"
        )

        extra_kwargs: dict[str, Any] = {}
        if self.provider in {"openai", "deepseek"}:
            extra_kwargs["response_format"] = {"type": "json_object"}
        if self.provider == "deepseek":
            extra_kwargs["thinking"] = {"type": "disabled"}

        try:
            response = self.provider_adapter.complete(
                model=self.model,
                system_prompt=DASHBOARD_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[],
                **extra_kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise AICallError(f"AI provider request failed: {exc}") from exc

        text = str(response.get("text", "")).strip()
        parsed = self._parse_dashboard_json(text)
        if parsed is None:
            raise AICallError("AI response is not valid dashboard JSON.")
        return self._coerce_dashboard_analysis(parsed, technical_summary=technical_summary)

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool calls and return a dict result."""
        handlers = {
            "get_price_data": self._handle_get_price_data,
            "calculate_indicators": self._handle_calculate_indicators,
            "get_support_resistance": self._handle_get_support_resistance,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}
        if not isinstance(tool_input, dict):
            return {"error": f"Tool input for {tool_name} must be an object."}
        try:
            return handler(**tool_input)
        except TypeError as exc:
            return {"error": f"Invalid arguments for {tool_name}: {exc}"}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def _build_dashboard_payload(
        self,
        *,
        symbol: str,
        technical_summary: Any,
        chip_summary: Any | None,
        company_info: dict[str, Any] | None,
        recent_prices: pd.DataFrame,
        market: str = "tw",
        currency: str = "TWD",
    ) -> dict[str, Any]:
        close_summary: dict[str, Any] = {}
        if isinstance(recent_prices, pd.DataFrame) and not recent_prices.empty and "close" in recent_prices.columns:
            close = pd.to_numeric(recent_prices["close"], errors="coerce").dropna()
            if not close.empty:
                close_summary = {
                    "latest_close": float(close.iloc[-1]),
                    "high_60d": float(close.tail(60).max()),
                    "low_60d": float(close.tail(60).min()),
                    "return_20d_pct": float(
                        ((close.iloc[-1] - close.iloc[-min(20, len(close))]) / close.iloc[-min(20, len(close))] * 100.0)
                        if len(close) >= 2 and close.iloc[-min(20, len(close))] != 0
                        else 0.0
                    ),
                }

        resistances = []
        supports = []
        for level in getattr(technical_summary, "resistance_levels", []) or []:
            resistances.append(
                {
                    "value": float(getattr(level, "value", 0.0)),
                    "label": str(getattr(level, "label", "")),
                }
            )
        for level in getattr(technical_summary, "support_levels", []) or []:
            supports.append(
                {
                    "value": float(getattr(level, "value", 0.0)),
                    "label": str(getattr(level, "label", "")),
                }
            )

        tech = {
            "trend_direction": str(getattr(technical_summary, "trend_direction", "")),
            "ma_status": str(getattr(technical_summary, "ma_status", "")),
            "kd_status": str(getattr(technical_summary, "kd_status", "")),
            "macd_status": str(getattr(technical_summary, "macd_status", "")),
            "volume_status": str(getattr(technical_summary, "volume_status", "")),
            "volume_price_relation": str(getattr(technical_summary, "volume_price_relation", "")),
            "short_term_score": float(getattr(technical_summary, "short_term_score", 0.0)),
            "short_term_label": str(getattr(technical_summary, "short_term_label", "")),
            "resistance_levels": resistances,
            "support_levels": supports,
            "operation_observation": str(getattr(technical_summary, "operation_observation", "")),
        }

        chip: dict[str, Any] | None = None
        if chip_summary is not None:
            chip = {
                "foreign_label": str(getattr(chip_summary, "foreign_label", "")),
                "trust_label": str(getattr(chip_summary, "trust_label", "")),
                "dealer_label": str(getattr(chip_summary, "dealer_label", "")),
                "chip_concentration": str(getattr(chip_summary, "chip_concentration", "")),
                "chip_trend": str(getattr(chip_summary, "chip_trend", "")),
                "chip_description": str(getattr(chip_summary, "chip_description", "")),
                "margin_balance_change": int(getattr(chip_summary, "margin_balance_change", 0)),
                "short_balance_change": int(getattr(chip_summary, "short_balance_change", 0)),
            }

        return {
            "symbol": str(symbol),
            "market": str(market),
            "currency": str(currency),
            "technical_summary": tech,
            "chip_summary": chip,
            "company_info": company_info or {},
            "recent_prices_summary": close_summary,
        }

    def _coerce_dashboard_analysis(self, payload: dict[str, Any], *, technical_summary: Any) -> DashboardAnalysis:
        fallback = self._fallback_scenarios(technical_summary)

        industry = payload.get("industry_overview", [])
        if not isinstance(industry, list):
            industry = []
        industry_out = [str(item).strip() for item in industry if str(item).strip()][:5]

        company = payload.get("company_overview", [])
        if not isinstance(company, list):
            company = []
        company_out = [str(item).strip() for item in company if str(item).strip()][:5]

        vpa = str(payload.get("volume_price_analysis", "")).strip()
        conclusion = str(payload.get("conclusion", "")).strip()

        raw_scenarios = payload.get("scenarios", [])
        scenarios_out: list[TradingScenario] = []
        if isinstance(raw_scenarios, list):
            for item in raw_scenarios:
                if not isinstance(item, dict):
                    continue
                scenarios_out.append(
                    TradingScenario(
                        name=str(item.get("name", "")).strip() or "情境",
                        entry_range=str(item.get("entry_range", "")).strip() or "依支撐壓力區間",
                        stop_loss=float(item.get("stop_loss", 0.0) or 0.0),
                        target=str(item.get("target", "")).strip() or "依壓力區分段",
                    )
                )
        scenarios_out = scenarios_out[:3]
        if len(scenarios_out) < 3:
            scenarios_out.extend(fallback[len(scenarios_out) : 3])

        if not industry_out:
            industry_out = ["產業資料不足，請搭配公開資訊觀察景氣循環。"]
        if not company_out:
            company_out = ["公司資料不足，請補充基本面與公告資訊。"]
        if not vpa:
            vpa = str(getattr(technical_summary, "operation_observation", "")).strip() or "量價資料不足。"
        if not conclusion:
            conclusion = "以上為研究情境推演，請依風險承受能力審慎評估。"

        return DashboardAnalysis(
            industry_overview=industry_out,
            company_overview=company_out,
            volume_price_analysis=vpa,
            scenarios=scenarios_out,
            conclusion=conclusion,
        )

    def _fallback_scenarios(self, technical_summary: Any) -> list[TradingScenario]:
        supports = [float(getattr(x, "value", 0.0)) for x in getattr(technical_summary, "support_levels", []) or []]
        resistances = [float(getattr(x, "value", 0.0)) for x in getattr(technical_summary, "resistance_levels", []) or []]
        support = min(supports) if supports else 0.0
        resistance = max(resistances) if resistances else support
        middle = (support + resistance) / 2.0 if resistance or support else 0.0

        def _fmt(v: float) -> str:
            return f"{v:.2f}"

        return [
            TradingScenario(
                name="開高走高",
                entry_range=f"{_fmt(middle)} ~ {_fmt(resistance)}",
                stop_loss=float(support),
                target=f"{_fmt(resistance)} / {_fmt(resistance * 1.03 if resistance else 0.0)}",
            ),
            TradingScenario(
                name="震盪整理",
                entry_range=f"{_fmt(support)} ~ {_fmt(middle)}",
                stop_loss=float(support * 0.98 if support else 0.0),
                target=f"{_fmt(middle)} / {_fmt(resistance)}",
            ),
            TradingScenario(
                name="開低回測",
                entry_range=f"{_fmt(support)} 附近",
                stop_loss=float(support * 0.97 if support else 0.0),
                target=f"{_fmt(middle)} / {_fmt(resistance)}",
            ),
        ]

    @staticmethod
    def _parse_dashboard_json(text: str) -> dict[str, Any] | None:
        body = str(text or "").strip()
        if not body:
            return None
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = body.find("{")
        end = body.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(body[start : end + 1])
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    def _handle_get_price_data(
        self,
        symbol: str,
        period: str,
        freq: str = "daily",
        market: str = "tw",
    ) -> dict[str, Any]:
        """Return capped OHLCV snapshots for AI tool usage."""
        normalized_market = normalize_market(market)
        try:
            normalized_symbol = normalize_symbol(symbol, market=normalized_market)
        except ValueError:
            return {"error": f"Invalid symbol format: {symbol}"}
        if freq not in SUPPORTED_FREQS:
            return {"error": f"Unsupported freq: {freq}"}

        if freq == "daily":
            df = self.storage.load_daily(normalized_symbol, market=normalized_market)
        else:
            df = self.storage.load_minute(normalized_symbol, market=normalized_market)

        if df.empty:
            return {"error": f"No local data for symbol: {normalized_symbol}"}

        out = df.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date")
        if out.empty:
            return {"error": f"No valid datetime rows for symbol: {normalized_symbol}"}

        target_rows = min(self._period_rows(period), 60)
        out = out.tail(target_rows)
        records = []
        for _, row in out.iterrows():
            records.append(
                {
                    "date": self._format_date(row["date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                    "symbol": str(row.get("symbol", normalized_symbol)),
                }
            )

        return {
            "symbol": normalized_symbol,
            "freq": freq,
            "data_count": len(records),
            "latest_date": records[-1]["date"] if records else None,
            "data": records,
        }

    def _handle_calculate_indicators(
        self,
        symbol: str,
        indicators: list[str],
        period: str = "6mo",
        market: str = "tw",
    ) -> dict[str, Any]:
        """Calculate a minimal set of indicators for phase 4-A tool calls."""
        normalized_market = normalize_market(market)
        try:
            normalized_symbol = normalize_symbol(symbol, market=normalized_market)
        except ValueError:
            return {"error": f"Invalid symbol format: {symbol}"}
        if not isinstance(indicators, list) or not indicators:
            return {"error": "indicators must be a non-empty list"}

        df = self.storage.load_daily(normalized_symbol, market=normalized_market)
        if df.empty:
            return {"error": f"No local data for symbol: {normalized_symbol}"}

        out = df.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date")
        if out.empty:
            return {"error": f"No valid datetime rows for symbol: {normalized_symbol}"}

        out = out.tail(self._period_rows(period))
        close = pd.to_numeric(out["close"], errors="coerce")
        result: dict[str, Any] = {}

        for indicator in indicators:
            name = str(indicator).strip().upper()
            if name.startswith("MA_"):
                try:
                    length = int(name.split("_", 1)[1])
                except Exception:  # noqa: BLE001
                    result[name] = {"error": "Invalid MA format"}
                    continue
                series = close.rolling(length).mean().dropna()
                result[name] = {
                    "latest": float(series.iloc[-1]) if not series.empty else None,
                    "prev_5": [float(v) for v in series.tail(5).tolist()],
                }
            elif name == "RSI_14":
                rsi = self._compute_rsi(close, length=14).dropna()
                result[name] = {
                    "latest": float(rsi.iloc[-1]) if not rsi.empty else None,
                    "prev_5": [float(v) for v in rsi.tail(5).tolist()],
                }
            elif name == "MACD":
                macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
                signal = macd_line.ewm(span=9, adjust=False).mean()
                hist = macd_line - signal
                result[name] = {
                    "macd": float(macd_line.iloc[-1]) if not macd_line.empty else None,
                    "signal": float(signal.iloc[-1]) if not signal.empty else None,
                    "histogram": float(hist.iloc[-1]) if not hist.empty else None,
                }
            else:
                result[name] = {"error": f"Unsupported indicator: {name}"}

        return {"symbol": normalized_symbol, "indicators": result}

    def _handle_get_support_resistance(self, symbol: str, lookback: int = 60, market: str = "tw") -> dict[str, Any]:
        """Compute simple support/resistance levels from local daily bars."""
        normalized_market = normalize_market(market)
        try:
            normalized_symbol = normalize_symbol(symbol, market=normalized_market)
        except ValueError:
            return {"error": f"Invalid symbol format: {symbol}"}
        if lookback <= 0:
            return {"error": "lookback must be positive"}

        df = self.storage.load_daily(normalized_symbol, market=normalized_market)
        if df.empty:
            return {"error": f"No local data for symbol: {normalized_symbol}"}

        out = df.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date").tail(lookback)
        if out.empty:
            return {"error": f"No valid datetime rows for symbol: {normalized_symbol}"}

        close = pd.to_numeric(out["close"], errors="coerce")
        high = pd.to_numeric(out["high"], errors="coerce")
        low = pd.to_numeric(out["low"], errors="coerce")

        current_price = float(close.iloc[-1])
        supports: list[dict[str, Any]] = [
            {"level": float(low.min()), "type": "recent_low"},
        ]
        resistances: list[dict[str, Any]] = [
            {"level": float(high.max()), "type": "recent_high"},
        ]

        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None
        if pd.notna(ma20):
            supports.append({"level": float(ma20), "type": "MA20"})
            resistances.append({"level": float(ma20), "type": "MA20"})
        if pd.notna(ma60):
            supports.append({"level": float(ma60), "type": "MA60"})
            resistances.append({"level": float(ma60), "type": "MA60"})

        return {
            "symbol": normalized_symbol,
            "current_price": current_price,
            "support_levels": sorted(supports, key=lambda x: x["level"]),
            "resistance_levels": sorted(resistances, key=lambda x: x["level"]),
        }

    def _append_disclaimer(self, text: str) -> str:
        body = str(text).strip()
        if "免責聲明" in body:
            return body
        if not body:
            return DISCLAIMER
        return f"{body}\n\n{DISCLAIMER}"

    def _resolve_api_key(self, provider: str, secrets: dict[str, Any]) -> str:
        if not isinstance(secrets, dict):
            return ""
        if provider == "anthropic":
            return str(secrets.get("anthropic_api_key", "")).strip()
        if provider == "openai":
            return str(secrets.get("openai_api_key", "")).strip()
        if provider == "gemini":
            gemini_key = str(secrets.get("gemini_api_key", "")).strip()
            if gemini_key:
                return gemini_key
            return str(secrets.get("google_api_key", "")).strip()
        if provider == "deepseek":
            return str(secrets.get("deepseek_api_key", "")).strip()
        return ""

    @staticmethod
    def _period_rows(period: str) -> int:
        normalized = str(period).strip().lower()
        return _PERIOD_TO_ROWS.get(normalized, 60)

    @staticmethod
    def _format_date(value: Any) -> str | None:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).strftime("%Y-%m-%d")

    @staticmethod
    def _compute_rsi(series: pd.Series, length: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(length).mean()
        avg_loss = loss.rolling(length).mean()
        rs = avg_gain / avg_loss.replace({0: pd.NA})
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(value, (int, float)):
            return bool(value)
        return False


def normalize_tool_calls_for_provider(provider: str, payload: Any) -> list[dict[str, Any]]:
    """Utility for tests: normalize tool calls with provider-specific adapter logic."""
    provider_name = str(provider).strip().lower()
    adapter_cls = PROVIDER_ADAPTERS.get(provider_name)
    if adapter_cls is None:
        raise ValueError(f"Unsupported AI provider: {provider}")

    # Use dummy constructor args for pure normalization tests.
    if provider_name == "anthropic":
        class _NoClientAnthropicAdapter(AnthropicAdapter):
            def __init__(self):
                self.api_key = ""
                self.model = ""
                self.timeout_seconds = 0.0

        adapter: BaseProviderAdapter = _NoClientAnthropicAdapter()
    else:
        adapter = adapter_cls(api_key="", model="")
    return [item.__dict__ for item in adapter.normalize_tool_calls(payload)]
