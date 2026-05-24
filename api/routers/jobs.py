"""Jobs router — /api/jobs/* endpoints.

Phase 10-A: skeleton lifecycle (create / poll / cancel / result).
Phase 10-C-2: added _run_data_job dispatcher for data_update / data_rebuild,
              proper write-lock acquisition, SSE stream endpoint.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
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
        "error": job.error,
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
    if request.type == "backtest_sweep":
        from src.services.backtest_service import BacktestServiceError, validate_sweep_request

        validated = validate_sweep_request(
            strategy_type=str(request.params.get("strategy_type", "")),
            param_candidates=request.params.get("param_candidates", {}),
        )
        if isinstance(validated, BacktestServiceError):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": validated.code,
                        "message": validated.message,
                    }
                },
            )
        request.params["strategy_type"] = validated["strategy_type"]
        request.params["param_candidates"] = validated["param_candidates"]

    if request.type == "backtest_wfa":
        import pandas as pd

        from src.backtest.walk_forward import required_months_for_wfa

        try:
            start = pd.Timestamp(str(request.params.get("start_date", "2020-01-01")))
            end = pd.Timestamp(str(request.params.get("end_date", "2024-12-31")))
        except Exception:  # noqa: BLE001
            start = pd.Timestamp("2020-01-01")
            end = pd.Timestamp("2024-12-31")

        is_months = int(request.params.get("is_months", 12))
        oos_months = int(request.params.get("oos_months", 3))
        step_months = int(request.params.get("step_months", 3))
        required = required_months_for_wfa(
            is_months=is_months,
            oos_months=oos_months,
            step_months=step_months,
        )
        actual = (end.year - start.year) * 12 + (end.month - start.month)
        if actual < required:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "INSUFFICIENT_DATA_FOR_WFA",
                        "message": (
                            f"資料日期區間不足：需要 {required} 個月，"
                            f"目前僅 {actual} 個月"
                        ),
                    }
                },
            )

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
    format: str | None = None,
    part: str | None = None,
    manager: JobManager = Depends(get_manager),
) -> Any:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )

    has_result = (job.status == "complete") or (job.status == "cancelled" and job.result is not None)
    if not has_result:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "JOB_NOT_COMPLETE",
                    "message": f"Job status is '{job.status}', not 'complete'",
                }
            },
        )

    if format == "csv":
        if job.result is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "JOB_NOT_COMPLETE",
                        "message": f"Job status is '{job.status}', not 'complete'",
                    }
                },
            )
        if job.type == "backtest_batch":
            from src.services.backtest_service import build_batch_csv_blob

            symbol = str(job.result.get("symbol", "symbol"))
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            filename = f"batch_{symbol}_{ts}.csv"
            blob = build_batch_csv_blob(job.result)
            return StreamingResponse(
                iter([blob.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if job.type == "backtest_sweep":
            from src.services.backtest_service import build_sweep_csv_blob

            symbol = str(job.result.get("symbol", "symbol"))
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            filename = f"sweep_{symbol}_{ts}.csv"
            blob = build_sweep_csv_blob(job.result)
            return StreamingResponse(
                iter([blob.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if job.type == "backtest_wfa":
            from src.services.backtest_service import (
                build_wfa_stability_csv_blob,
                build_wfa_window_csv_blob,
            )

            symbol = str(job.result.get("symbol", "symbol"))
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            if part == "stability":
                filename = f"wfa_stability_{symbol}_{ts}.csv"
                blob = build_wfa_stability_csv_blob(job.result)
            else:
                filename = f"wfa_window_{symbol}_{ts}.csv"
                blob = build_wfa_window_csv_blob(job.result)
            return StreamingResponse(
                iter([blob.getvalue()]),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "CSV_UNSUPPORTED",
                    "message": f"CSV export is not supported for job type '{job.type}'",
                }
            },
        )

    if job.status == "complete":
        return {"data": job.result or {}, "meta": {"job_id": job_id, "status": job.status}}
    return {"data": job.result, "meta": {"job_id": job_id, "status": "cancelled"}}


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
        elif job.type == "backtest_batch":
            await _run_backtest_batch_job(manager, job, params)
        elif job.type == "backtest_sweep":
            await _run_backtest_sweep_job(manager, job, params)
        elif job.type == "backtest_wfa":
            await _run_backtest_wfa_job(manager, job, params)
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
    from src.services.data_service import (
        DataServiceError,
        list_symbols,
        refresh_shareholder_meeting_once_per_day,
        run_maintenance,
    )

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
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
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

            sym_warnings = getattr(result, "warnings", [])
            if not isinstance(sym_warnings, list):
                sym_warnings = []
            for w in sym_warnings:
                warnings.append({"symbol": symbol, "message": w})

            sym_errors = getattr(result, "errors", [])
            if not isinstance(sym_errors, list):
                sym_errors = []
            for e in sym_errors:
                errors.append({"symbol": symbol, "message": e})

            manager.push_event(job.id, "progress", {
                "current": i,
                "total": total,
                "current_symbol": symbol,
                "status": "done",
                "warnings": sym_warnings,
                "errors": sym_errors,
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

    shareholder_refreshed = False
    current = manager.get_job(job.id)
    if market == "tw" and not (current and current.status == "cancelled"):
        shareholder_refreshed = await asyncio.to_thread(
            refresh_shareholder_meeting_once_per_day,
            market,
        )

    final_result: dict[str, Any] = {
        "succeeded": succeeded,
        "failed": failed,
        "warnings": warnings,
        "errors": errors,
        "shareholder_meeting_refreshed": shareholder_refreshed,
    }
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


async def _run_backtest_batch_job(
    manager: JobManager, job: Job, params: dict[str, Any]
) -> None:
    """Runner for backtest_batch job type (Phase 10-E-2)."""
    import pandas as pd

    from src.services.backtest_service import (
        BacktestServiceError,
        list_strategy_presets,
        run_batch_backtest_job,
    )

    presets = list_strategy_presets()
    raw_indices = params.get("strategy_preset_indices")
    selected_indices: list[int]
    if raw_indices is None:
        selected_indices = list(range(len(presets)))
    elif isinstance(raw_indices, list):
        selected_indices = []
        for item in raw_indices:
            if not isinstance(item, int) or item < 0 or item >= len(presets):
                manager.fail_job(
                    job.id,
                    error={"code": "INVALID_PARAMS", "message": "strategy_preset_indices out of range"},
                )
                return
            if item not in selected_indices:
                selected_indices.append(item)
    else:
        manager.fail_job(
            job.id,
            error={"code": "INVALID_PARAMS", "message": "strategy_preset_indices must be a list"},
        )
        return

    if not selected_indices:
        manager.fail_job(
            job.id,
            error={"code": "INVALID_PARAMS", "message": "No strategy selected"},
        )
        return

    total = len(selected_indices)
    summaries: list[dict[str, Any]] = []
    shared_price_data: list[dict[str, Any]] = []

    symbol = str(params.get("symbol", ""))
    market = str(params.get("market", "tw"))
    start_date = str(params.get("start_date", "2020-01-01"))
    end_date = str(params.get("end_date", "2024-12-31"))
    initial_capital = float(params.get("initial_capital", 1_000_000))

    for i, preset_index in enumerate(selected_indices, 1):
        current = manager.get_job(job.id)
        if current and current.status == "cancelled":
            break

        preset = presets[preset_index]
        manager.push_event(job.id, "progress", {
            "current": i,
            "total": total,
            "preset_index": preset_index,
            "preset_name": str(preset.get("name", "")),
            "status": "running",
        })
        manager.update_job(
            job.id,
            progress=(i - 0.5) / total,
            message=f"策略比較中：{preset.get('name', '')}",
        )

        partial = await asyncio.to_thread(
            run_batch_backtest_job,
            symbol=symbol,
            start_ts=pd.Timestamp(start_date),
            end_exclusive=pd.Timestamp(end_date) + pd.Timedelta(days=1),
            presets=[preset],
            market=market,
            initial_capital=initial_capital,
        )

        if isinstance(partial, BacktestServiceError):
            manager.fail_job(
                job.id,
                error={"code": partial.code, "message": partial.message},
            )
            return

        if not shared_price_data:
            shared_price_data = partial.get("price_data", [])

        summary = (partial.get("summaries") or [{}])[0]
        summary["preset_index"] = preset_index
        summaries.append(summary)

        manager.push_event(job.id, "progress", {
            "current": i,
            "total": total,
            "preset_index": preset_index,
            "preset_name": str(preset.get("name", "")),
            "status": "done",
            "error": summary.get("error"),
        })

    success_count = len([s for s in summaries if not s.get("error")])
    failed_count = len(summaries) - success_count
    payload = {
        "symbol": symbol,
        "market": market,
        "currency": "USD" if str(market).lower() == "us" else "TWD",
        "engine": "vectorized",
        "start_date": start_date,
        "end_date": end_date,
        "total_presets": total,
        "completed_presets": len(summaries),
        "success_count": success_count,
        "failed_count": failed_count,
        "price_data": shared_price_data,
        "summaries": summaries,
    }

    manager.push_event(job.id, "result", payload)
    current = manager.get_job(job.id)
    if current and current.status == "cancelled":
        manager.finish_cancelled_job(job.id, result=payload)
    else:
        manager.complete_job(job.id, result=payload)


async def _run_backtest_sweep_job(
    manager: JobManager, job: Job, params: dict[str, Any]
) -> None:
    """Runner for backtest_sweep job type (Phase 10-E-3)."""
    import pandas as pd

    from src.services.backtest_service import (
        BacktestServiceError,
        run_sweep_job,
    )

    strategy_type = str(params.get("strategy_type", "")).strip().lower()
    raw_candidates = params.get("param_candidates")
    if not isinstance(raw_candidates, dict):
        manager.fail_job(
            job.id,
            error={"code": "INVALID_PARAMS", "message": "param_candidates must be an object"},
        )
        return

    manager.update_job(job.id, progress=0.02, message="參數掃描啟動中…")

    def _on_progress(current: int, total: int, current_params: dict[str, Any]) -> None:
        manager.push_event(job.id, "progress", {
            "current": current,
            "total": total,
            "current_params": current_params,
            "status": "running",
        })
        manager.update_job(
            job.id,
            progress=max(0.02, current / total) if total > 0 else 0.02,
            message=f"參數掃描中：{current}/{total}",
        )

    def _should_cancel() -> bool:
        current = manager.get_job(job.id)
        return bool(current and current.status == "cancelled")

    payload = await asyncio.to_thread(
        run_sweep_job,
        symbol=str(params.get("symbol", "")),
        start_ts=pd.Timestamp(str(params.get("start_date", "2020-01-01"))),
        end_exclusive=pd.Timestamp(str(params.get("end_date", "2024-12-31")))
        + pd.Timedelta(days=1),
        strategy_type=strategy_type,
        param_candidates=raw_candidates,
        market=str(params.get("market", "tw")),
        initial_capital=float(params.get("initial_capital", 1_000_000)),
        on_progress=_on_progress,
        should_cancel=_should_cancel,
    )

    if isinstance(payload, BacktestServiceError):
        manager.fail_job(
            job.id,
            error={"code": payload.code, "message": payload.message},
        )
        return

    manager.push_event(job.id, "result", payload)
    current = manager.get_job(job.id)
    if current and current.status == "cancelled":
        manager.finish_cancelled_job(job.id, result=payload)
    else:
        manager.complete_job(job.id, result=payload)


async def _run_backtest_wfa_job(
    manager: JobManager, job: Job, params: dict[str, Any]
) -> None:
    """Runner for backtest_wfa job type (Phase 10-E-4)."""
    import pandas as pd

    from src.services.backtest_service import (
        BacktestServiceError,
        run_walk_forward_job,
    )

    manager.update_job(job.id, progress=0.02, message="Walk-Forward 分析啟動中…")

    def _on_window_progress(
        *,
        window_id: int,
        total_windows: int,
        phase: str,
        best_params: Any = None,
        oos_sharpe: Any = None,
    ) -> None:
        data: dict[str, Any] = {
            "window_id": window_id,
            "total_windows": total_windows,
            "phase": phase,
        }
        if best_params is not None:
            data["best_params"] = best_params
        if oos_sharpe is not None:
            data["oos_sharpe"] = oos_sharpe
        manager.push_event(job.id, "window_progress", data)
        if phase == "done" and total_windows > 0:
            manager.update_job(
                job.id,
                progress=window_id / total_windows,
                message=f"WFA 進度：{window_id}/{total_windows} 段視窗",
            )

    def _on_sweep_progress(
        *,
        window_id: int,
        current: int,
        total: int,
        current_params: dict[str, Any],
    ) -> None:
        manager.push_event(job.id, "sweep_progress", {
            "window_id": window_id,
            "current": current,
            "total": total,
            "current_params": current_params,
        })

    def _should_cancel() -> bool:
        current = manager.get_job(job.id)
        return bool(current and current.status == "cancelled")

    payload = await asyncio.to_thread(
        run_walk_forward_job,
        symbol=str(params.get("symbol", "")),
        start_ts=pd.Timestamp(str(params.get("start_date", "2020-01-01"))),
        end_exclusive=pd.Timestamp(str(params.get("end_date", "2024-12-31")))
        + pd.Timedelta(days=1),
        strategy_type=str(params.get("strategy_type", "")),
        param_candidates=params.get("param_candidates", {}),
        is_months=int(params.get("is_months", 12)),
        oos_months=int(params.get("oos_months", 3)),
        step_months=int(params.get("step_months", 3)),
        optimize_metric=str(params.get("optimize_metric", "sharpe_ratio")),
        market=str(params.get("market", "tw")),
        initial_capital=float(params.get("initial_capital", 1_000_000)),
        on_window_progress=_on_window_progress,
        on_sweep_progress=_on_sweep_progress,
        should_cancel=_should_cancel,
    )

    if isinstance(payload, BacktestServiceError):
        manager.fail_job(
            job.id,
            error={"code": payload.code, "message": payload.message},
        )
        return

    manager.push_event(job.id, "result", payload)
    current = manager.get_job(job.id)
    if current and current.status == "cancelled":
        manager.finish_cancelled_job(job.id, result=payload)
    else:
        manager.complete_job(job.id, result=payload)
