"""Tests for Active ETF API endpoints (Phase 16-B)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.core.exceptions import FetcherError

client = TestClient(app)


def _reset_manager() -> None:
    import api.job_manager as jm
    jm._job_manager = None


def test_get_active_etf_list_returns_schema() -> None:
    _reset_manager()
    mock_list = [{"code": "00981A", "name": "主動統一台股增長"}]
    with patch("src.services.active_etf_service.ActiveEtfService.get_list", return_value=mock_list):
        resp = client.get("/api/active-etf/list")
    assert resp.status_code == 200
    body = resp.json()
    assert "etfs" in body
    assert body["etfs"] == mock_list


def test_get_active_etf_list_graceful_fallback() -> None:
    _reset_manager()
    with patch("src.services.active_etf_service.ActiveEtfService.get_list", side_effect=Exception("Mocked error")):
        resp = client.get("/api/active-etf/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["etfs"] == []


def test_get_active_etf_holdings_invalid_code_format() -> None:
    _reset_manager()
    # Not 5 digits + A
    resp = client.get("/api/active-etf/1234/holdings")
    assert resp.status_code == 422

    resp = client.get("/api/active-etf/00981/holdings")
    assert resp.status_code == 422

    resp = client.get("/api/active-etf/00981AB/holdings")
    assert resp.status_code == 422


def test_get_active_etf_holdings_success() -> None:
    _reset_manager()
    mock_result = {
        "etf_code": "00981A",
        "etf_name": "主動統一台股增長",
        "latest_date": "2026-06-04",
        "previous_date": "2026-06-03",
        "has_previous": True,
        "holdings": [],
        "changes": {
            "buys": [],
            "sells": [],
            "entries": [],
            "exits": [],
        },
    }
    with patch("src.services.active_etf_service.ActiveEtfService.get_holdings_with_diff", return_value=mock_result):
        resp = client.get("/api/active-etf/00981a/holdings")
    assert resp.status_code == 200
    assert resp.json() == mock_result


def test_get_active_etf_holdings_write_lock_isolated() -> None:
    """Verify that holdings endpoint does NOT get blocked by the global job_manager write lock."""
    _reset_manager()
    from api.job_manager import get_job_manager
    mgr = get_job_manager()

    async def _hold() -> None:
        await mgr._write_lock.acquire()

    # Acquire global lock in async loop
    asyncio.run(_hold())

    mock_result = {
        "etf_code": "00981A",
        "etf_name": "主動統一台股增長",
        "latest_date": "2026-06-04",
        "previous_date": "2026-06-03",
        "has_previous": True,
        "holdings": [],
        "changes": {
            "buys": [],
            "sells": [],
            "entries": [],
            "exits": [],
        },
    }

    try:
        with patch("src.services.active_etf_service.ActiveEtfService.get_holdings_with_diff", return_value=mock_result):
            resp = client.get("/api/active-etf/00981A/holdings")
        assert resp.status_code == 200
        assert resp.json() == mock_result
    finally:
        mgr.release_write_lock()


def test_get_active_etf_holdings_fetcher_error() -> None:
    _reset_manager()
    with patch("src.services.active_etf_service.ActiveEtfService.get_holdings_with_diff", side_effect=FetcherError("Mocked network error")):
        resp = client.get("/api/active-etf/00981A/holdings")
    assert resp.status_code == 502
    assert "擷取資料失敗" in resp.json()["detail"]["error"]["message"]


def test_get_active_etf_holdings_general_exception() -> None:
    _reset_manager()
    with patch("src.services.active_etf_service.ActiveEtfService.get_holdings_with_diff", side_effect=Exception("Mocked system error")):
        resp = client.get("/api/active-etf/00981A/holdings")
    assert resp.status_code == 500
    assert "系統處理錯誤" in resp.json()["detail"]["error"]["message"]


def test_get_active_etf_holdings_on_view_dedup(tmp_path, monkeypatch) -> None:
    _reset_manager()
    monkeypatch.setattr("src.data.storage.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("src.core.config.get_data_dir", lambda: tmp_path)

    from src.data.storage import ParquetStorage
    from src.services.active_etf_service import _HOLDINGS_CACHE
    import pandas as pd
    from datetime import date

    etf = "00981A"
    snapshot_date = date(2026, 6, 4)
    df_data = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 100, "weight_pct": 10.0}
    ])

    mock_fetch = lambda self, code: (snapshot_date, df_data)
    monkeypatch.setattr("src.data.fetcher.MoneyDjActiveEtfSource.fetch_holdings", mock_fetch)

    mock_list = lambda self: pd.DataFrame([{"etf_code": etf, "etf_name": "主動統一台股增長"}])
    monkeypatch.setattr("src.data.fetcher.MoneyDjActiveEtfSource.fetch_list", mock_list)

    if etf in _HOLDINGS_CACHE:
        del _HOLDINGS_CACHE[etf]

    resp1 = client.get(f"/api/active-etf/{etf}/holdings")
    assert resp1.status_code == 200

    storage = ParquetStorage(data_dir=tmp_path)
    loaded1 = storage.load_active_etf_holdings(etf)
    assert len(loaded1) == 1

    if etf in _HOLDINGS_CACHE:
        del _HOLDINGS_CACHE[etf]

    resp2 = client.get(f"/api/active-etf/{etf}/holdings")
    assert resp2.status_code == 200

    loaded2 = storage.load_active_etf_holdings(etf)
    assert len(loaded2) == 1


def test_trigger_sweep_api(monkeypatch) -> None:
    """Verify that POST /sweep starts background sweep and returns 202."""
    _reset_manager()
    from src.services.active_etf_service import ActiveEtfService
    import api.routers.active_etf as router_mod

    # Mock sweep_all to prevent real execution/delay
    sweep_called_with = None
    def mock_sweep_all(self, skip_code=None):
        nonlocal sweep_called_with
        sweep_called_with = skip_code
    monkeypatch.setattr(ActiveEtfService, "sweep_all", mock_sweep_all)

    # Ensure flag is initially False
    router_mod._sweep_running = False

    # 1. First trigger -> 202 started
    resp = client.post("/api/active-etf/sweep?skip_code=00981A")
    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}
    assert sweep_called_with == "00981A"

    # 2. Manually set running flag to True to simulate concurrent execution
    router_mod._sweep_running = True
    resp_dup = client.post("/api/active-etf/sweep")
    assert resp_dup.status_code == 202
    assert resp_dup.json() == {"status": "already_running"}

    # Reset running flag for other tests
    router_mod._sweep_running = False
