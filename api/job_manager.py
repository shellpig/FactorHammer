"""In-memory Job Manager with write-lock support (Phase 10-A).

Design notes:
- Single asyncio.Lock (_write_lock) prevents concurrent write-type jobs.
- Jobs expire after ttl_seconds (default 30 min); cleanup is lazy.
- Write-type job types: data_fetch, data_rebuild, backtest_run,
  backtest_batch, backtest_sweep, backtest_wfa.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_WRITE_JOB_TYPES: frozenset[str] = frozenset(
    {
        "data_fetch",
        "data_rebuild",
        "backtest_run",
        "backtest_batch",
        "backtest_sweep",
        "backtest_wfa",
    }
)


@dataclass
class Job:
    id: str
    type: str
    status: str          # "pending" | "running" | "complete" | "error" | "cancelled"
    progress: float      # 0.0 ~ 1.0
    message: str
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: datetime
    ttl_seconds: int = 1800   # 30 minutes

    def is_write_type(self) -> bool:
        return self.type in _WRITE_JOB_TYPES

    def is_expired(self) -> bool:
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds


class JobManager:
    """Thread-safe in-memory job manager backed by asyncio.Lock."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._write_lock: asyncio.Lock = asyncio.Lock()

    # ── public API ─────────────────────────────────────────────────────────

    async def create_job(self, job_type: str, params: dict[str, Any]) -> Job:
        """Create a new job.  Write-type jobs must call acquire_write_lock() first."""
        job = Job(
            id=str(uuid.uuid4()),
            type=job_type,
            status="pending",
            progress=0.0,
            message="等待中…",
            result=None,
            error=None,
            created_at=datetime.now(timezone.utc),
        )
        self._jobs[job.id] = job
        return job

    async def acquire_write_lock(self) -> bool:
        """Try to acquire the write lock without waiting.

        Returns True if acquired, False if already held.
        Caller is responsible for releasing via release_write_lock().
        """
        acquired = self._write_lock.locked()
        if acquired:
            return False
        await self._write_lock.acquire()
        return True

    def release_write_lock(self) -> None:
        """Release the write lock (no-op if not held)."""
        if self._write_lock.locked():
            try:
                self._write_lock.release()
            except RuntimeError:
                pass

    def is_write_locked(self) -> bool:
        return self._write_lock.locked()

    def get_job(self, job_id: str) -> Job | None:
        self.cleanup_expired()
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = float(progress)
        if message is not None:
            job.message = message
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        return job

    async def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in ("complete", "error"):
            return False
        job.status = "cancelled"
        return True

    def cleanup_expired(self) -> None:
        expired = [jid for jid, j in self._jobs.items() if j.is_expired()]
        for jid in expired:
            del self._jobs[jid]

    def all_jobs(self) -> list[Job]:
        self.cleanup_expired()
        return list(self._jobs.values())


# Singleton instance shared across the FastAPI app
_job_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
