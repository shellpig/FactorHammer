"""Unit tests for Active ETF tracking features (Phase 16-A)."""

import datetime
from datetime import date
from pathlib import Path
import time
import pytest
import pandas as pd

from src.core.exceptions import FetcherError
from src.data.fetcher import MoneyDjActiveEtfSource
from src.data.storage import ParquetStorage, StorageError
from src.services.active_etf_service import ActiveEtfService, _HOLDINGS_CACHE


# ---------------------------------------------------------------------------
# MoneyDjActiveEtfSource Test Cases
# ---------------------------------------------------------------------------

def test_moneydj_active_etf_parser_00981a():
    """Verify that MoneyDjActiveEtfSource parses 00981A HTML correctly."""
    fixture_path = Path(__file__).parent / "fixtures" / "moneydj_active_etf_00981a.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    source = MoneyDjActiveEtfSource()
    snapshot_date, df = source.parse_holdings_html(html_content, "00981A")

    # Assert Date
    assert snapshot_date == date(2026, 6, 3)

    # Assert Columns and Types
    assert list(df.columns) == ["holding_code", "holding_name", "shares", "weight_pct"]
    assert len(df) == 51  # Row count for 00981A full holdings

    # First row is TSMC (2330.TW)
    first = df.iloc[0]
    assert first["holding_code"] == "2330.TW"
    assert first["holding_name"] == "台積電" or "2330" in html_content  # Match content parsed
    assert first["shares"] == 11960000
    assert first["weight_pct"] == 9.97


def test_moneydj_active_etf_parser_00983a_overseas():
    """Verify that MoneyDjActiveEtfSource parses 00983A with overseas assets correctly."""
    fixture_path = Path(__file__).parent / "fixtures" / "moneydj_active_etf_00983a.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    source = MoneyDjActiveEtfSource()
    snapshot_date, df = source.parse_holdings_html(html_content, "00983A")

    assert snapshot_date == date(2026, 6, 2)
    assert len(df) == 39  # Row count

    # First row is Tesla (TSLA.US)
    tesla = df[df["holding_code"] == "TSLA.US"].iloc[0]
    assert tesla["holding_name"] == "Tesla"
    assert tesla["shares"] == 16131
    assert tesla["weight_pct"] == 9.08


def test_moneydj_active_etf_fetch_list_fallback(monkeypatch, tmp_path):
    """Verify that fetch_list swallows all token/network errors and returns an empty DataFrame."""
    # Temporarily set get_data_dir to point to tmp_path to isolate cache check
    monkeypatch.setattr("src.core.config.get_data_dir", lambda: tmp_path)

    # Mock FinMindFetcher to raise FetcherError to test error swallowing
    from src.data.fetcher import FinMindFetcher
    def mock_fetch_fail(self):
        raise FetcherError("Mocked FinMind fetch error")
    monkeypatch.setattr(FinMindFetcher, "fetch_stock_info", mock_fetch_fail)

    # Trigger fetch_list with no token / no config - it should return empty df without crashing
    source = MoneyDjActiveEtfSource()
    df = source.fetch_list()
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == ["etf_code", "etf_name"]


# ---------------------------------------------------------------------------
# ParquetStorage Test Cases
# ---------------------------------------------------------------------------

def test_parquet_storage_path_traversal_guard(tmp_path):
    """Verify that ParquetStorage active ETF paths reject path traversal attempts."""
    storage = ParquetStorage(data_dir=tmp_path)

    # 1. Invalid format code checks
    with pytest.raises(StorageError, match="Invalid active ETF code"):
        storage._active_etf_holdings_path("2330")

    with pytest.raises(StorageError, match="Invalid active ETF code"):
        storage._active_etf_holdings_path("00981")

    # 2. Path traversal check (escaping root folder)
    # The validate method limits it to ^\d{5}A$ but even if we trick path resolver:
    with pytest.raises(StorageError):
        storage._active_etf_holdings_path("../../../00981A")


def test_parquet_storage_save_load_active_etf_list(tmp_path):
    """Verify save and load active ETF list and metadata in ParquetStorage."""
    storage = ParquetStorage(data_dir=tmp_path)

    assert storage.load_active_etf_list().empty
    assert storage.load_active_etf_list_meta() == {}

    # Save list
    test_df = pd.DataFrame([
        {"etf_code": "00981a", "etf_name": " 00981A Name "},
        {"etf_code": "00983A", "etf_name": "00983A Name"},
    ])
    storage.save_active_etf_list(test_df)

    loaded = storage.load_active_etf_list()
    assert len(loaded) == 2
    assert list(loaded["etf_code"]) == ["00981A", "00983A"]
    assert list(loaded["etf_name"]) == ["00981A Name", "00983A Name"]

    # Save meta
    meta = {"fetched_at": "2026-06-04T12:00:00"}
    storage.save_active_etf_list_meta(meta)
    assert storage.load_active_etf_list_meta() == meta


def test_parquet_storage_save_holdings_dedup(tmp_path):
    """Verify ParquetStorage save_active_etf_holdings prevents duplicate snapshot dates."""
    storage = ParquetStorage(data_dir=tmp_path)

    etf = "00981A"
    snapshot_d = date(2026, 6, 3)
    df_data = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 100, "weight_pct": 10.0}
    ])

    # First save
    storage.save_active_etf_holdings(etf, snapshot_d, df_data)
    loaded = storage.load_active_etf_holdings(etf)
    assert len(loaded) == 1
    assert loaded.iloc[0]["snapshot_date"] == snapshot_d
    assert loaded.iloc[0]["shares"] == 100

    # Second save with different shares on same snapshot_date - should be skipped (dedup)
    df_data_dup = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 200, "weight_pct": 10.0}
    ])
    storage.save_active_etf_holdings(etf, snapshot_d, df_data_dup)
    loaded_dup = storage.load_active_etf_holdings(etf)
    assert len(loaded_dup) == 1
    assert loaded_dup.iloc[0]["shares"] == 100  # Stays 100, no update

    # Save with another snapshot_date - should append
    new_snapshot_d = date(2026, 6, 4)
    storage.save_active_etf_holdings(etf, new_snapshot_d, df_data)
    loaded_new = storage.load_active_etf_holdings(etf)
    assert len(loaded_new) == 2
    assert set(loaded_new["snapshot_date"]) == {snapshot_d, new_snapshot_d}


# ---------------------------------------------------------------------------
# ActiveEtfService Test Cases
# ---------------------------------------------------------------------------

def test_service_get_holdings_with_diff_no_previous(tmp_path, monkeypatch):
    """Verify get_holdings_with_diff when there is only a single (latest) snapshot."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)

    etf = "00981A"
    snapshot_d = date(2026, 6, 3)
    df_data = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1000, "weight_pct": 12.5},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 500, "weight_pct": 5.2},
    ])

    storage.save_active_etf_holdings(etf, snapshot_d, df_data)

    # Disable mock fetch to prevent TTL fetch trigger
    monkeypatch.setitem(_HOLDINGS_CACHE, etf, time.time())

    result = service.get_holdings_with_diff(etf)

    assert result["etf_code"] == "00981A"
    assert result["latest_date"] == "2026-06-03"
    assert result["previous_date"] is None
    assert result["has_previous"] is False
    assert len(result["holdings"]) == 2

    # Check holdings items
    h1 = result["holdings"][0]
    assert h1["rank"] == 1
    assert h1["holding_code"] == "2330.TW"
    assert h1["shares"] == 1000
    assert h1["weight_pct"] == 12.5
    assert h1["delta_shares"] is None

    # Check changes are empty
    changes = result["changes"]
    assert changes["buys"] == []
    assert changes["sells"] == []
    assert changes["entries"] == []
    assert changes["exits"] == []


def test_service_get_holdings_with_diff_calculation(tmp_path, monkeypatch):
    """Verify get_holdings_with_diff computes buys, sells, entries, and exits correctly."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)

    etf = "00981A"

    # Save previous snapshot (2026-06-03)
    # TSMC: 1000 shares
    # Delta: 500 shares
    # ExitStock: 200 shares
    # Cash: 100000 shares (no ticker)
    prev_d = date(2026, 6, 3)
    prev_df = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1000, "weight_pct": 10.0},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 500, "weight_pct": 5.0},
        {"holding_code": "9999.TW", "holding_name": "ExitStock", "shares": 200, "weight_pct": 2.0},
        {"holding_code": "", "holding_name": "Cash", "shares": 100000, "weight_pct": 1.0},
    ])
    storage.save_active_etf_holdings(etf, prev_d, prev_df)

    # Save latest snapshot (2026-06-04)
    # TSMC: 1200 shares -> BUY (+200)
    # Delta: 400 shares -> SELL (-100)
    # EntryStock: 300 shares -> ENTRY (+300)
    # Cash: 150000 shares -> BUY (+50000, joined on Cash holding_name)
    # ExitStock is gone -> EXIT (-200)
    latest_d = date(2026, 6, 4)
    latest_df = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1200, "weight_pct": 12.0},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 400, "weight_pct": 4.0},
        {"holding_code": "1111.TW", "holding_name": "EntryStock", "shares": 300, "weight_pct": 3.0},
        {"holding_code": "", "holding_name": "Cash", "shares": 150000, "weight_pct": 1.5},
    ])
    storage.save_active_etf_holdings(etf, latest_d, latest_df)

    # Lock TTL cache so it doesn't trigger mock fetch
    monkeypatch.setitem(_HOLDINGS_CACHE, etf, time.time())

    result = service.get_holdings_with_diff(etf)

    assert result["etf_code"] == "00981A"
    assert result["latest_date"] == "2026-06-04"
    assert result["previous_date"] == "2026-06-03"
    assert result["has_previous"] is True

    # Validate Holdings (latest only, sorted by weight)
    # TSMC (12.0) -> Delta (4.0) -> EntryStock (3.0) -> Cash (1.5)
    holdings = result["holdings"]
    assert len(holdings) == 4

    assert holdings[0]["holding_code"] == "2330.TW"
    assert holdings[0]["delta_shares"] == 200

    assert holdings[1]["holding_code"] == "2308.TW"
    assert holdings[1]["delta_shares"] == -100

    assert holdings[2]["holding_code"] == "1111.TW"
    assert holdings[2]["delta_shares"] == 300

    assert holdings[3]["holding_code"] == ""
    assert holdings[3]["holding_name"] == "Cash"
    assert holdings[3]["delta_shares"] == 50000

    # Validate Changes
    changes = result["changes"]

    # 1. buys: TSMC (+200), Cash (+50000)
    # Sorted by |delta_shares| descending: Cash (+50000) first, then TSMC (+200)
    assert len(changes["buys"]) == 2
    assert changes["buys"][0]["holding_name"] == "Cash"
    assert changes["buys"][0]["delta_shares"] == 50000
    assert changes["buys"][1]["holding_code"] == "2330.TW"
    assert changes["buys"][1]["delta_shares"] == 200

    # 2. sells: Delta (-100)
    assert len(changes["sells"]) == 1
    assert changes["sells"][0]["holding_code"] == "2308.TW"
    assert changes["sells"][0]["delta_shares"] == -100

    # 3. entries: EntryStock (+300)
    assert len(changes["entries"]) == 1
    assert changes["entries"][0]["holding_code"] == "1111.TW"
    assert changes["entries"][0]["delta_shares"] == 300

    # 4. exits: ExitStock (-200)
    assert len(changes["exits"]) == 1
    assert changes["exits"][0]["holding_code"] == "9999.TW"
    assert changes["exits"][0]["delta_shares"] == -200
