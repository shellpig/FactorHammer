"""Tests for data_service (Phase 10-A)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.data_service import (
    DataServiceError,
    MaintenanceReport,
    SymbolStatus,
    get_symbol_status,
    list_symbols,
    run_maintenance,
)


# ---------------------------------------------------------------------------
# list_symbols
# ---------------------------------------------------------------------------


@patch("src.services.data_service.DuckDBMeta")
def test_list_symbols_tw_filters_market(mock_meta_cls: MagicMock) -> None:
    mock_meta = MagicMock()
    mock_meta.list_all.return_value = pd.DataFrame(
        {
            "symbol": ["2330", "AAPL"],
            "market": ["tw", "us"],
            "first_date": ["2020-01-01", "2020-01-01"],
            "last_date": ["2024-01-01", "2024-01-01"],
        }
    )
    mock_meta_cls.return_value = mock_meta

    result = list_symbols(market="tw")
    assert len(result) == 1
    assert result[0]["symbol"] == "2330"


@patch("src.services.data_service.DuckDBMeta")
def test_list_symbols_us_filters_market(mock_meta_cls: MagicMock) -> None:
    mock_meta = MagicMock()
    mock_meta.list_all.return_value = pd.DataFrame(
        {
            "symbol": ["2330", "AAPL"],
            "market": ["tw", "us"],
            "first_date": ["2020-01-01", "2020-01-01"],
            "last_date": ["2024-01-01", "2024-01-01"],
        }
    )
    mock_meta_cls.return_value = mock_meta

    result = list_symbols(market="us")
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


@patch("src.services.data_service.DuckDBMeta")
def test_list_symbols_returns_empty_on_error(mock_meta_cls: MagicMock) -> None:
    mock_meta_cls.side_effect = RuntimeError("db error")
    result = list_symbols(market="tw")
    assert result == []


# ---------------------------------------------------------------------------
# get_symbol_status
# ---------------------------------------------------------------------------


@patch("src.services.data_service.ParquetStorage")
def test_get_symbol_status_returns_two_entries(mock_storage_cls: MagicMock) -> None:
    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=5, freq="B"), "close": [100.0] * 5}
    )
    mock_storage.load_adjusted.return_value = pd.DataFrame()
    mock_storage_cls.return_value = mock_storage

    result = get_symbol_status("AAPL", market="us")
    assert len(result) == 2
    types = {s.data_type for s in result}
    assert "raw_daily" in types
    assert "adjusted_daily" in types


@patch("src.services.data_service.ParquetStorage")
def test_get_symbol_status_raw_daily_available(mock_storage_cls: MagicMock) -> None:
    df = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=10, freq="B"), "close": [100.0] * 10}
    )
    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = df
    mock_storage.load_adjusted.return_value = pd.DataFrame()
    mock_storage_cls.return_value = mock_storage

    statuses = get_symbol_status("2330", market="tw")
    raw = next(s for s in statuses if s.data_type == "raw_daily")
    assert raw.available is True
    assert raw.row_count == 10
    assert raw.start_date != "-"
    assert raw.end_date != "-"


@patch("src.services.data_service.ParquetStorage")
def test_get_symbol_status_adjusted_unavailable(mock_storage_cls: MagicMock) -> None:
    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=5, freq="B"), "close": [100.0] * 5}
    )
    mock_storage.load_adjusted.return_value = pd.DataFrame()
    mock_storage_cls.return_value = mock_storage

    statuses = get_symbol_status("2330", market="tw")
    adj = next(s for s in statuses if s.data_type == "adjusted_daily")
    assert adj.available is False
    assert adj.row_count == 0


# ---------------------------------------------------------------------------
# run_maintenance
# ---------------------------------------------------------------------------


@patch("src.services.data_service._build_fetchers_from_config")
@patch("src.services.data_service.ParquetStorage")
@patch("src.services.data_service.DuckDBMeta")
@patch("src.services.data_service.DataMaintenance")
def test_run_maintenance_update_calls_update_daily(
    mock_maintenance_cls: MagicMock,
    mock_meta_cls: MagicMock,
    mock_storage_cls: MagicMock,
    mock_build_fetchers: MagicMock,
) -> None:
    mock_fetcher = MagicMock()
    mock_build_fetchers.return_value = [("yfinance", mock_fetcher)]
    mock_maintenance = MagicMock()
    mock_maintenance.update_daily.return_value = 5
    mock_maintenance_cls.return_value = mock_maintenance
    mock_meta_cls.return_value = MagicMock()
    mock_storage_cls.return_value = MagicMock()

    result = run_maintenance("AAPL", rebuild=False, market="us")
    assert isinstance(result, MaintenanceReport)
    assert result.operation == "update"
    assert result.rows_added == 5
    assert result.success is True


@patch("src.services.data_service._build_fetchers_from_config")
def test_run_maintenance_returns_error_when_no_source(mock_build_fetchers: MagicMock) -> None:
    mock_build_fetchers.return_value = []
    result = run_maintenance("AAPL", market="us")
    assert isinstance(result, DataServiceError)
    assert result.code == "NO_SOURCE"


@patch("src.services.data_service._build_fetchers_from_config")
@patch("src.services.data_service.ParquetStorage")
@patch("src.services.data_service.DuckDBMeta")
@patch("src.services.data_service.DataMaintenance")
def test_run_maintenance_update_us_calls_market_us(
    mock_maintenance_cls: MagicMock,
    mock_meta_cls: MagicMock,
    mock_storage_cls: MagicMock,
    mock_build_fetchers: MagicMock,
) -> None:
    mock_fetcher = MagicMock()
    mock_build_fetchers.return_value = [("yfinance", mock_fetcher)]
    mock_maintenance = MagicMock()
    mock_maintenance.update_daily.return_value = 3
    mock_maintenance_cls.return_value = mock_maintenance
    mock_meta_cls.return_value = MagicMock()
    mock_storage_cls.return_value = MagicMock()

    run_maintenance("AAPL", rebuild=False, market="us")
    mock_maintenance.update_daily.assert_called_once_with("AAPL", market="us")
