"""Jobs router — /api/jobs/* endpoints (Phase 10-A).

Job lifecycle:
  POST /api/jobs          → create job, return job_id
  GET  /api/jobs/{id}     → poll job status
  GET  /api/jobs/{id}/events  → SSE progress stream (10-E onwards)
  GET  /api/jobs/{id}/result  → completed job result
  POST /api/jobs/{id}/cancel  → cancel running job
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_manager
from api.job_manager import Job, JobManager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class CreateJobRequest(BaseModel):
    type: str
    params: dict[str, Any] = {}


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    type: str


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

    Write-type jobs (data_fetch, backtest_run, etc.) require the write lock.
    Returns 409 if the lock is currently held.
    """
    from api.job_manager import _WRITE_JOB_TYPES  # noqa: PLC0415

    is_write = request.type in _WRITE_JOB_TYPES
    if is_write and manager.is_write_locked():
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

    # Immediately start a background task for supported job types.
    # For now only "dummy" is supported in 10-A; real runners will be added in 10-E.
    asyncio.create_task(_run_job(manager, job, request.params))  # noqa: RUF006

    return _job_to_response(job)


@router.get("/{job_id}")
def get_job(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}})
    return _job_to_response(job)


@router.get("/{job_id}/result")
def get_job_result(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}})
    if job.status != "complete":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "JOB_NOT_COMPLETE", "message": f"Job status is '{job.status}', not 'complete'"}},
        )
    return {"data": job.result or {}, "meta": {"job_id": job_id}}


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    manager: JobManager = Depends(get_manager),
) -> dict[str, Any]:
    cancelled = await manager.cancel_job(job_id)
    if not cancelled:
        job = manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}})
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "JOB_NOT_CANCELLABLE", "message": f"Job status is '{job.status}'"}},
        )
    return {"data": {"status": "cancelled"}, "meta": {"job_id": job_id}}


# ---------------------------------------------------------------------------
# Background task dispatcher (10-A skeleton — only "dummy" type)
# ---------------------------------------------------------------------------


async def _run_job(manager: JobManager, job: Job, params: dict[str, Any]) -> None:
    """Dispatch job to appropriate runner.

    Real runners (backtest, data_fetch, etc.) will be wired up in 10-E/10-C.
    """
    manager.update_job(job.id, status="running", progress=0.1, message="啟動中…")

    if job.type == "dummy":
        await _run_dummy_job(manager, job)
    else:
        # Placeholder for future job types — mark as error for now
        manager.update_job(
            job.id,
            status="error",
            progress=0.0,
            message=f"尚未實作的 job type: {job.type}",
            error={"code": "NOT_IMPLEMENTED", "message": f"Job type '{job.type}' is not yet implemented"},
        )


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
