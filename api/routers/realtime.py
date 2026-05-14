"""Realtime router — TW quote and US intraday snapshot endpoints."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import math
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.services.dashboard_service import DashboardError, build_dashboard_payload

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


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


@router.get("/tw")
def get_tw_realtime(symbol: str) -> dict[str, Any]:
    result = build_dashboard_payload(symbol=symbol, market="tw")
    if isinstance(result, DashboardError):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": result.code, "message": result.message}},
        )
    if result.quote is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "REALTIME_UNAVAILABLE",
                    "message": "台股即時報價暫時不可用。",
                }
            },
        )
    return {
        "data": {
            "quote": _to_jsonable(result.quote),
            "bid_ask": _to_jsonable(result.bid_ask),
        },
        "meta": {"symbol": result.symbol, "market": result.market},
    }


@router.get("/us/intraday")
def get_us_intraday(symbol: str) -> dict[str, Any]:
    result = build_dashboard_payload(symbol=symbol, market="us")
    if isinstance(result, DashboardError):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": result.code, "message": result.message}},
        )
    if result.intraday_snapshot is None and result.intraday_df.empty:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "INTRADAY_UNAVAILABLE",
                    "message": result.intraday_error or "美股分K資料暫時不可用。",
                }
            },
        )
    return {
        "data": {
            "intraday_snapshot": _to_jsonable(result.intraday_snapshot),
            "intraday_df": _to_jsonable(result.intraday_df),
            "intraday_error": result.intraday_error,
        },
        "meta": {"symbol": result.symbol, "market": result.market},
    }
