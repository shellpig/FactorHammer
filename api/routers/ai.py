"""AI router — dashboard analysis trigger endpoint."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import math
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.dashboard_service import DashboardError, build_dashboard_payload

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    symbol: str
    market: str = "tw"
    bars: int = 250


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
