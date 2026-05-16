"""Jobs router — /api/jobs/* endpoints.

Phase 10-A: skeleton lifecycle (create / poll / cancel / result).
Phase 10-C-2: added _run_data_job dispatcher for data_update / data_rebuild,
              proper write-lock acquisition, SSE stream endpoint.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_manager
from api.job_manager import Job, JobManager, _WRITE_JOB_TYPES

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class CreateJobRequest(BaseModel):
    type: str
    params: dict[str, Any] = {}


def _job_to_response(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "created_at": job.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_job(
    request: CreateJobRequest,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    """Create a new job.

    Write-type jobs require the write lock — returns 409 if locked.
    The background runner releases the lock when done.
    """
    is_write = request.type in _WRITE_JOB_TYPES
    if is_write:
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

    job = await manager.create_job(request.type, request.params)
    asyncio.create_task(_run_job(manager, job, request.params))  # noqa: RUF006
    return _job_to_response(job)


@router.get("/{job_id}")
def get_job(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )
    return _job_to_response(job)


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    manager: JobManager = Depends(get_manager),
) -> StreamingResponse:
    """SSE stream of progress / result events for a job.

    Events:
      progress — { current, total, current_symbol, status, error? }
      result   — { succeeded, failed }
    """
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    queue = manager.get_events_queue(job_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Event queue for {job_id} not found"}},
        )

    async def generate():  # type: ignore[return]
        while True:
            if await request.is_disconnected():
                break
            try:
                item: dict[str, Any] | None = await asyncio.wait_for(queue.get(), timeout=15.0)
                if item is None:  # sentinel — job ended
                    break
                yield f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/result")
def get_job_result(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )
    # Allow "complete" and "cancelled with partial result"
    if job.status == "complete":
        return {"data": job.result or {}, "meta": {"job_id": job_id, "status": job.status}}
    if job.status == "cancelled" and job.result is not None:
        return {"data": job.result, "meta": {"job_id": job_id, "status": "cancelled"}}
    raise HTTPException(
        status_code=409,
        detail={
            "error": {
                "code": "JOB_NOT_COMPLETE",
                "message": f"Job status is '{job.status}', not 'complete'",
            }
        },
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    cancelled = await manager.cancel_job(job_id)
    if not cancelled:
        job = manager.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
            )
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "JOB_NOT_CANCELLABLE",
                    "message": f"Job status is '{job.status}'",
                }
            },
        )
    return {"data": {"status": "cancelled"}, "meta": {"job_id": job_id}}


# ---------------------------------------------------------------------------
# Background task dispatcher
# ---------------------------------------------------------------------------


async def _run_job(manager: JobManager, job: Job, params: dict[str, Any]) -> None:
    """Dispatch job to appropriate runner; release write-lock when done."""
    manager.update_job(job.id, status="running", progress=0.05, message="啟動中…")

    try:
        if job.type in ("data_update", "data_rebuild"):
            await _run_data_job(manager, job, params)
        elif job.type == "backtest_run":
            await _run_backtest_run_job(manager, job, params)
        elif job.type == "dummy":
            await _run_dummy_job(manager, job)
        else:
            manager.update_job(
                job.id,
                status="error",
                progress=0.0,
                message=f"尚未實作的 job type: {job.type}",
                error={
                    "code": "NOT_IMPLEMENTED",
                    "message": f"Job type '{job.type}' is not yet implemented",
                },
            )
            manager._close_event_queue(job.id)
    except Exception as exc:  # noqa: BLE001
        manager.fail_job(job.id, error={"code": "RUNNER_ERROR", "message": str(exc)})
    finally:
        if job.is_write_type():
            manager.release_write_lock()


async def _run_data_job(manager: JobManager, job: Job, params: dict[str, Any]) -> None:
    """Runner for data_update and data_rebuild job types.

    Single-file failures do NOT abort the batch — they are recorded in `failed`.
    """
    from src.services.data_service import DataServiceError, list_symbols, run_maintenance

    market = params.get("market", "tw")
    rebuild = (job.type == "data_rebuild")

    # Resolve target symbols
    if params.get("all"):
        raw = list_symbols(market=market)
        symbols: list[str] = [
            (r["symbol"] if isinstance(r, dict) else str(r)) for r in raw
        ]
    else:
        symbols = [str(s) for s in (params.get("symbols") or [])]

    if not symbols:
        manager.fail_job(job.id, error={"code": "NO_TARGETS", "message": "未指定任何 symbol"})
        return

    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    total = len(symbols)

    for i, symbol in enumerate(symbols, 1):
        # Check for cancellation between files
        current = manager.get_job(job.id)
        if current and current.status == "cancelled":
            break

        manager.push_event(job.id, "progress", {
            "current": i,
            "total": total,
            "current_symbol": symbol,
            "status": "updating",
        })
        manager.update_job(
            job.id,
            progress=(i - 0.5) / total,
            message=f"{'重建' if rebuild else '更新'} {symbol}…",
        )

        try:
            result = await asyncio.to_thread(
                run_maintenance, symbol, rebuild=rebuild, market=market
            )
            if isinstance(result, DataServiceError):
                raise RuntimeError(result.message)
            succeeded.append(symbol)
            manager.push_event(job.id, "progress", {
                "current": i,
                "total": total,
                "current_symbol": symbol,
                "status": "done",
            })
        except Exception as exc:  # noqa: BLE001
            err_str = str(exc)
            failed.append({"symbol": symbol, "error": err_str})
            manager.push_event(job.id, "progress", {
                "current": i,
                "total": total,
                "current_symbol": symbol,
                "status": "failed",
                "error": err_str,
            })

    final_result: dict[str, Any] = {"succeeded": succeeded, "failed": failed}
    manager.push_event(job.id, "result", final_result)
    manager.complete_job(job.id, result=final_result)


async def _run_dummy_job(manager: JobManager, job: Job) -> None:
    """Simulated job for testing the job lifecycle (10-A)."""
    for pct in (0.25, 0.5, 0.75, 1.0):
        if manager.get_job(job.id) and manager.get_job(job.id).status == "cancelled":  # type: ignore[union-attr]
            return
        await asyncio.sleep(0.1)
        manager.update_job(job.id, progress=pct, message=f"進度 {int(pct * 100)}%…")

    manager.update_job(
        job.id,
        status="complete",
        progress=1.0,
        message="完成",
        result={"ok": True, "params": job.type},
    )
    manager._close_event_queue(job.id)


async def _run_backtest_run_job(
    manager: JobManager, job: Job, params: dict[str, Any]
) -> None:
    """Runner for backtest_run job type (Phase 10-E-1)."""
    import pandas as pd

    from src.services.backtest_service import (
        BacktestServiceError,
        list_strategy_presets,
        run_backtest_job,
        serialize_backtest_result,
    )

    presets = list_strategy_presets()
    idx = params.get("strategy_preset_index")
    if not isinstance(idx, int) or idx < 0 or idx >= len(presets):
        manager.fail_job(
            job.id,
            error={"code": "INVALID_PARAMS", "message": "strategy_preset_index out of range"},
        )
        return

    if manager.get_job(job.id) and manager.get_job(job.id).status == "cancelled":  # type: ignore[union-attr]
        return

    manager.push_event(job.id, "progress", {"status": "running", "phase": "loading_data"})

    initial_capital = float(params.get("initial_capital", 1_000_000))

    result = await asyncio.to_thread(
        run_backtest_job,
        symbol=str(params.get("symbol", "")),
        start_ts=pd.Timestamp(str(params.get("start_date", "2020-01-01"))),
        end_exclusive=pd.Timestamp(str(params.get("end_date", "2024-12-31")))
        + pd.Timedelta(days=1),
        strategy_preset=presets[idx],
        engine=str(params.get("engine", "vectorized")),
        market=str(params.get("market", "tw")),
        initial_capital=initial_capital,
    )

    if isinstance(result, BacktestServiceError):
        manager.fail_job(
            job.id, error={"code": result.code, "message": result.message}
        )
        return

    payload = serialize_backtest_result(result)
    manager.push_event(job.id, "result", payload)

    current = manager.get_job(job.id)
    if current and current.status == "cancelled":
        manager.finish_cancelled_job(job.id, result=payload)
    else:
        manager.complete_job(job.id, result=payload)
