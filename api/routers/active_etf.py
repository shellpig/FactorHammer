"""Active ETF router — /api/active-etf/* endpoints (Phase 16-B)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_manager
from api.job_manager import JobManager
from src.core.exceptions import FetcherError
from src.services.active_etf_service import ActiveEtfService

router = APIRouter(prefix="/api/active-etf", tags=["active_etf"])


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
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    """Get holdings and difference details for a specific active ETF.

    Guarded by write lock.
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
    finally:
        manager.release_write_lock()
