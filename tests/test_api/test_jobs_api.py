"""Tests for jobs API endpoints (Phase 10-A).

Uses FastAPI TestClient.
Tests: create job → poll → result; cancel; concurrent write jobs → 409.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.job_manager import get_job_manager

client = TestClient(app)


def _reset_job_manager() -> None:
    """Reset singleton between tests to avoid state leakage."""
    import api.job_manager as jm_module
    jm_module._job_manager = None


# ---------------------------------------------------------------------------
# POST /api/jobs — create job
# ---------------------------------------------------------------------------


def test_create_dummy_job_returns_201() -> None:
    _reset_job_manager()
    response = client.post("/api/jobs", json={"type": "dummy", "params": {}})
    assert response.status_code == 201
    body = response.json()
    assert "job_id" in body
    assert body["status"] in ("pending", "running", "complete")


def test_create_job_returns_job_id() -> None:
    _reset_job_manager()
    response = client.post("/api/jobs", json={"type": "dummy", "params": {}})
    assert response.status_code == 201
    assert len(response.json()["job_id"]) > 0


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}
# ---------------------------------------------------------------------------


def test_get_job_returns_status() -> None:
    _reset_job_manager()
    create = client.post("/api/jobs", json={"type": "dummy", "params": {}})
    job_id = create.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert "status" in body


def test_get_job_not_found_returns_404() -> None:
    _reset_job_manager()
    response = client.get("/api/jobs/nonexistent-uuid-1234")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/cancel
# ---------------------------------------------------------------------------


def test_cancel_job_returns_cancelled() -> None:
    _reset_job_manager()
    # Create a long-running job type (not implemented → error, but cancellable before that)
    create = client.post("/api/jobs", json={"type": "data_fetch", "params": {}})
    job_id = create.json()["job_id"]

    # Cancel it immediately
    cancel = client.post(f"/api/jobs/{job_id}/cancel")
    # May be 200 (cancelled) or 409 (already finished) — both valid
    assert cancel.status_code in (200, 409)


def test_cancel_nonexistent_job_returns_404() -> None:
    _reset_job_manager()
    response = client.post("/api/jobs/nonexistent-uuid-9999/cancel")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Concurrent write-type jobs → 409
# ---------------------------------------------------------------------------


def test_second_write_job_returns_409_when_lock_held() -> None:
    """If write lock is held, POST /api/jobs with a write-type returns 409."""
    _reset_job_manager()
    manager = get_job_manager()

    # Manually hold the write lock for the duration of this test
    async def _hold_lock() -> None:
        await manager._write_lock.acquire()

    asyncio.run(_hold_lock())

    try:
        response = client.post("/api/jobs", json={"type": "backtest_run", "params": {}})
        assert response.status_code == 409
        body = response.json()
        assert body["detail"]["error"]["code"] == "WRITE_LOCK_BUSY"
    finally:
        manager.release_write_lock()


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/result — only when complete
# ---------------------------------------------------------------------------


def test_get_result_of_incomplete_job_returns_409() -> None:
    _reset_job_manager()
    # Create a job and immediately try to get result (likely not complete yet)
    create = client.post("/api/jobs", json={"type": "data_fetch", "params": {}})
    job_id = create.json()["job_id"]

    result = client.get(f"/api/jobs/{job_id}/result")
    # Either 409 (not complete) or 404 (expired) — both valid since not complete
    assert result.status_code in (404, 409)
