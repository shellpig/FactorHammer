"""Active ETF router — /api/active-etf/* endpoints (Phase 16-B)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException

from src.core.exceptions import FetcherError
from src.services.active_etf_service import ActiveEtfService

router = APIRouter(prefix="/api/active-etf", tags=["active_etf"])

_sweep_running = False


@router.get("/list")
def get_active_etf_list() -> dict[str, Any]:
    """Get the list of active ETFs."""
    try:
        service = ActiveEtfService()
        etfs = service.get_list()
        return {"etfs": etfs}
    except Exception:
        return {"etfs": []}


@router.get("/{code}/holdings")
async def get_active_etf_holdings(
    code: str,
) -> dict[str, Any]:
    """Get holdings and difference details for a specific active ETF.

    Guarded by per-ETF Lock inside service layer.
    """
    normalized_code = code.strip().upper()
    if not re.match(r"^\d{5}A$", normalized_code):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_CODE",
                    "message": "無效的 ETF 代碼格式，必須為 5 位數字加 A",
                }
            },
        )

    try:
        service = ActiveEtfService()
        result = service.get_holdings_with_diff(normalized_code)
        return result
    except FetcherError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "FETCH_ERROR",
                    "message": f"擷取資料失敗: {exc}",
                }
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SYSTEM_ERROR",
                    "message": f"系統處理錯誤: {exc}",
                }
            },
        ) from exc


@router.post("/sweep", status_code=202)
async def trigger_sweep(skip_code: str | None = None) -> dict[str, Any]:
    """Trigger background active ETF holdings sweep.

    Immediately returns 202 to the client.
    """
    global _sweep_running

    if _sweep_running:
        return {"status": "already_running"}

    normalized_skip = None
    if skip_code:
        skip_code_clean = skip_code.strip().upper()
        if re.match(r"^\d{5}A$", skip_code_clean):
            normalized_skip = skip_code_clean

    _sweep_running = True

    def run_sweep():
        global _sweep_running
        try:
            service = ActiveEtfService()
            service.sweep_all(skip_code=normalized_skip)
        finally:
            _sweep_running = False

    # Run in background thread using asyncio.to_thread to avoid blocking event loop
    asyncio.create_task(asyncio.to_thread(run_sweep))

    return {"status": "started"}
