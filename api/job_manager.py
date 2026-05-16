"""In-memory Job Manager with write-lock and SSE event queue support.

Phase 10-A: core lifecycle (create / poll / cancel / cleanup).
Phase 10-C-2: added data_update write-type, push_event/fail_job/complete_job,
              per-job asyncio.Queue for SSE streaming.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_WRITE_JOB_TYPES: frozenset[str] = frozenset(
    {
        "data_update",
        "data_rebuild",
        "data_fetch",
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
    params: dict[str, Any] = field(default_factory=dict)
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
        # Per-job event queues for SSE streaming (None sentinel closes the stream)
        self._event_queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}

    # ── write-lock helpers ─────────────────────────────────────────────────

    async def acquire_write_lock(self) -> bool:
        """Try to acquire the write lock without waiting.

        Returns True if acquired, False if already held.
        Caller is responsible for releasing via release_write_lock().
        """
        if self._write_lock.locked():
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

    # ── job lifecycle ──────────────────────────────────────────────────────

    async def create_job(self, job_type: str, params: dict[str, Any]) -> Job:
        """Create a new job with a fresh event queue."""
        job = Job(
            id=str(uuid.uuid4()),
            type=job_type,
            status="pending",
            progress=0.0,
            message="等待中…",
            result=None,
            error=None,
            created_at=datetime.now(timezone.utc),
            params=params,
        )
        self._jobs[job.id] = job
        self._event_queues[job.id] = asyncio.Queue()
        return job

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
        # Do NOT close the event queue here; finish_cancelled_job() handles that
        # after the service layer pushes any partial result event.
        return True

    def finish_cancelled_job(self, job_id: str, result: dict[str, Any]) -> None:
        """Store partial result for a cancelled job and close the SSE stream."""
        self.update_job(
            job_id,
            status="cancelled",
            result=result,
            message="已取消",
        )
        self._close_event_queue(job_id)

    def cleanup_expired(self) -> None:
        expired = [jid for jid, j in self._jobs.items() if j.is_expired()]
        for jid in expired:
            del self._jobs[jid]
            self._event_queues.pop(jid, None)

    def all_jobs(self) -> list[Job]:
        self.cleanup_expired()
        return list(self._jobs.values())

    # ── SSE event queue ────────────────────────────────────────────────────

    def push_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Push an SSE event into the job's queue."""
        queue = self._event_queues.get(job_id)
        if queue is not None:
            queue.put_nowait({"type": event_type, "data": data})

    def get_events_queue(self, job_id: str) -> asyncio.Queue[dict[str, Any] | None] | None:
        return self._event_queues.get(job_id)

    def fail_job(self, job_id: str, error: dict[str, Any]) -> None:
        """Mark job as error and close the SSE stream."""
        self.update_job(job_id, status="error", error=error, message="錯誤")
        self._close_event_queue(job_id)

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None:
        """Mark job as complete and close the SSE stream."""
        self.update_job(job_id, status="complete", progress=1.0, result=result, message="完成")
        self._close_event_queue(job_id)

    def _close_event_queue(self, job_id: str) -> None:
        """Send None sentinel to the SSE queue so the stream generator exits."""
        queue = self._event_queues.get(job_id)
        if queue is not None:
            queue.put_nowait(None)


# Singleton instance shared across the FastAPI app
_job_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
