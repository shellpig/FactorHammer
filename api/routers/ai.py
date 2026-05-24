"""AI router — dashboard analysis trigger + chat lock endpoints."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
import math
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.deps import get_advisor
from src.ai.advisor import AIAdvisor
from src.core.config import get_config
from src.services.config_service import get_secrets_status
from src.services.dashboard_service import DashboardError, build_dashboard_payload

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    symbol: str
    market: str = "tw"
    bars: int = 250


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# ── 15-B streaming endpoints ───────────────────────────────────────────────


@router.get("/status")
def get_ai_status() -> dict:
    config = get_config()
    ai_config = config.get("ai", {}) if isinstance(config, dict) else {}
    enabled = bool(ai_config.get("enabled", True))
    provider = str(ai_config.get("provider", "anthropic")).lower()

    if not enabled:
        return {
            "available": False,
            "reason": "ai_disabled",
            "message": "AI 功能已關閉（ai.enabled=false）。",
        }

    secrets_status = get_secrets_status()
    has_key = secrets_status.get(provider, False)
    if not has_key:
        return {
            "available": False,
            "reason": "missing_key",
            "message": f"目前 provider 為 {provider}，但 .env 內找不到對應 API key。",
        }

    return {
        "available": True,
        "reason": "ok",
        "message": "OK",
    }


@router.post("/chat")
async def post_ai_chat(
    request: ChatRequest,
    advisor: AIAdvisor = Depends(get_advisor),
) -> EventSourceResponse:
    async def event_generator():
        messages_dict = [m.model_dump() for m in request.messages]
        try:
            async for chunk in advisor.stream_chat(messages_dict):
                event = chunk.get("event", "token")
                if event == "token":
                    yield {
                        "event": "token",
                        "data": json.dumps({"text": chunk["text"]}),
                    }
                elif event == "tool_call":
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "name": chunk["name"],
                            "arguments": chunk["arguments"],
                        }),
                    }
                elif event == "tool_result":
                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "name": chunk["name"],
                            "output_summary": chunk["output_summary"],
                        }),
                    }
                elif event == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": chunk["message"]}),
                    }
            yield {
                "event": "done",
                "data": "{}",
            }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}),
            }

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, pd.DataFrame):
        return [_to_jsonable(item) for item in value.to_dict(orient="records")]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if pd.isna(value):
        return None
    return value


@router.post("/analyze")
def post_ai_analyze(request: AnalyzeRequest) -> dict[str, Any]:
    result = build_dashboard_payload(
        symbol=request.symbol,
        market=request.market,
        bars=request.bars,
    )
    if isinstance(result, DashboardError):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": result.code, "message": result.message}},
        )
    if not result.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "AI_DISABLED",
                    "message": "AI 功能目前未啟用。",
                }
            },
        )
    if result.analysis is None:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "AI_ANALYSIS_FAILED",
                    "message": "AI 分析失敗，請稍後重試。",
                }
            },
        )

    return {
        "data": _to_jsonable(result.analysis),
        "meta": {"symbol": result.symbol, "market": result.market},
    }
