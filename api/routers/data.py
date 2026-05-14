"""Data router — /api/data/* endpoints (Phase 10-A skeleton)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_manager
from api.job_manager import JobManager
from src.services.data_service import (
    DataServiceError,
    get_symbol_status,
    list_symbols,
)

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/symbols")
def get_symbols(market: str = "tw") -> dict[str, Any]:
    """List all locally stored symbols for the given market."""
    symbols = list_symbols(market=market)
    return {"data": symbols, "meta": {"market": market, "count": len(symbols)}}


@router.get("/status/{market}/{symbol}")
def get_data_status(market: str, symbol: str) -> dict[str, Any]:
    """Return raw + adjusted data status for a symbol."""
    statuses = get_symbol_status(symbol, market=market)
    return {
        "data": [
            {
                "symbol": s.symbol,
                "market": s.market,
                "data_type": s.data_type,
                "available": s.available,
                "row_count": s.row_count,
                "start_date": s.start_date,
                "end_date": s.end_date,
            }
            for s in statuses
        ],
        "meta": {"market": market, "symbol": symbol},
    }


@router.delete("/{market}/{symbol}")
async def delete_symbol(
    market: str,
    symbol: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    """Delete all local data for a symbol.

    Requires write lock — returns 409 if another operation is in progress.
    Does NOT delete data/backtest/ results.
    """
    from src.services.data_service import delete_symbol_data

    if manager.is_write_locked():
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "WRITE_LOCK_BUSY",
                    "message": "目前有其他資料操作正在進行，請稍後再試",
                }
            },
        )

    acquired = await manager.acquire_write_lock()
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "WRITE_LOCK_BUSY",
                    "message": "目前有其他資料操作正在進行，請稍後再試",
                }
            },
        )

    try:
        result = delete_symbol_data(symbol, market=market)
        if isinstance(result, DataServiceError):
            if result.code == "NOT_FOUND":
                raise HTTPException(status_code=404, detail={"error": {"code": result.code, "message": result.message}})
            raise HTTPException(status_code=500, detail={"error": {"code": result.code, "message": result.message}})
        return {"data": {"deleted": True, "symbol": symbol, "market": market}, "meta": {}}
    finally:
        manager.release_write_lock()
