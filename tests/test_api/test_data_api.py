"""Tests for data API endpoints (Phase 10-C-1).

Covers: GET /symbols, GET /status, DELETE — success, 404, 409 (write-lock).
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _reset_manager() -> None:
    import api.job_manager as jm
    jm._job_manager = None


# ---------------------------------------------------------------------------
# GET /api/data/symbols
# ---------------------------------------------------------------------------


def test_get_symbols_returns_envelope() -> None:
    _reset_manager()
    with patch("api.routers.data.list_symbols", return_value=[{"symbol": "2330", "market": "tw"}]):
        resp = client.get("/api/data/symbols?market=tw")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert isinstance(body["data"], list)


def test_get_symbols_meta_market() -> None:
    _reset_manager()
    with patch("api.routers.data.list_symbols", return_value=[]):
        resp = client.get("/api/data/symbols?market=tw")
    assert resp.json()["meta"]["market"] == "tw"


def test_get_symbols_count_in_meta() -> None:
    _reset_manager()
    rows = [{"symbol": "2330", "market": "tw"}, {"symbol": "2317", "market": "tw"}]
    with patch("api.routers.data.list_symbols", return_value=rows):
        resp = client.get("/api/data/symbols?market=tw")
    assert resp.json()["meta"]["count"] == 2


def test_get_symbols_us_market() -> None:
    _reset_manager()
    with patch("api.routers.data.list_symbols", return_value=[{"symbol": "AAPL", "market": "us"}]):
        resp = client.get("/api/data/symbols?market=us")
    assert resp.status_code == 200
    assert resp.json()["meta"]["market"] == "us"


def test_get_symbols_empty_returns_empty_list() -> None:
    _reset_manager()
    with patch("api.routers.data.list_symbols", return_value=[]):
        resp = client.get("/api/data/symbols?market=tw")
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["count"] == 0


# ---------------------------------------------------------------------------
# GET /api/data/status/{market}/{symbol}
# ---------------------------------------------------------------------------


def _make_status(symbol: str, market: str, data_type: str, available: bool, rows: int = 0):
    from src.services.data_service import SymbolStatus
    return SymbolStatus(
        symbol=symbol,
        market=market,
        data_type=data_type,
        available=available,
        row_count=rows,
        start_date="2010-01-04" if available else "-",
        end_date="2026-05-14" if available else "-",
    )


def test_get_status_returns_two_entries() -> None:
    _reset_manager()
    mock = [
        _make_status("2330", "tw", "raw_daily", True, 4012),
        _make_status("2330", "tw", "adjusted_daily", False),
    ]
    with patch("api.routers.data.get_symbol_status", return_value=mock):
        resp = client.get("/api/data/status/tw/2330")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2


def test_get_status_data_types() -> None:
    _reset_manager()
    mock = [
        _make_status("2330", "tw", "raw_daily", True, 4012),
        _make_status("2330", "tw", "adjusted_daily", False),
    ]
    with patch("api.routers.data.get_symbol_status", return_value=mock):
        resp = client.get("/api/data/status/tw/2330")
    types = {e["data_type"] for e in resp.json()["data"]}
    assert "raw_daily" in types
    assert "adjusted_daily" in types


def test_get_status_fields_present() -> None:
    _reset_manager()
    mock = [_make_status("AAPL", "us", "raw_daily", True, 4115)]
    with patch("api.routers.data.get_symbol_status", return_value=mock):
        resp = client.get("/api/data/status/us/AAPL")
    entry = resp.json()["data"][0]
    for field in ("symbol", "market", "data_type", "available", "row_count", "start_date", "end_date"):
        assert field in entry, f"Missing field: {field}"


def test_get_status_available_true() -> None:
    _reset_manager()
    mock = [_make_status("AAPL", "us", "raw_daily", True, 4115)]
    with patch("api.routers.data.get_symbol_status", return_value=mock):
        resp = client.get("/api/data/status/us/AAPL")
    assert resp.json()["data"][0]["available"] is True
    assert resp.json()["data"][0]["row_count"] == 4115


def test_get_status_meta_contains_symbol() -> None:
    _reset_manager()
    mock = [_make_status("2330", "tw", "raw_daily", True)]
    with patch("api.routers.data.get_symbol_status", return_value=mock):
        resp = client.get("/api/data/status/tw/2330")
    assert resp.json()["meta"]["symbol"] == "2330"


# ---------------------------------------------------------------------------
# DELETE /api/data/{market}/{symbol}
# ---------------------------------------------------------------------------


def test_delete_symbol_success() -> None:
    _reset_manager()
    with patch("src.services.data_service.delete_symbol_data", return_value=True):
        resp = client.delete("/api/data/tw/2330")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["deleted"] is True
    assert body["data"]["symbol"] == "2330"
    assert body["data"]["market"] == "tw"


def test_delete_symbol_not_found_returns_404() -> None:
    _reset_manager()
    from src.services.data_service import DataServiceError
    err = DataServiceError(code="NOT_FOUND", message="Symbol not found")
    with patch("src.services.data_service.delete_symbol_data", return_value=err):
        resp = client.delete("/api/data/tw/9999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"


def test_delete_symbol_409_when_write_lock_busy() -> None:
    _reset_manager()
    from api.job_manager import get_job_manager
    mgr = get_job_manager()

    async def _hold() -> None:
        await mgr._write_lock.acquire()

    asyncio.run(_hold())
    try:
        resp = client.delete("/api/data/tw/2330")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "WRITE_LOCK_BUSY"
    finally:
        mgr.release_write_lock()


def test_delete_releases_write_lock_on_success() -> None:
    """Write lock must be released after a successful DELETE."""
    _reset_manager()
    from api.job_manager import get_job_manager
    with patch("src.services.data_service.delete_symbol_data", return_value=True):
        resp = client.delete("/api/data/tw/2330")
    assert resp.status_code == 200
    mgr = get_job_manager()
    # Lock should be free — we can acquire it
    assert not mgr.is_write_locked()
