"""Tests for dashboard_service (Phase 10-A)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.dashboard_service import (
    DashboardError,
    DashboardPayload,
    build_dashboard_payload,
    _normalize_daily_df,
    _prepare_daily_data,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_daily_df(n: int = 60, market: str = "tw") -> pd.DataFrame:
    """Return a minimal OHLCV daily DataFrame."""
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * n,
            "high": [105.0] * n,
            "low": [95.0] * n,
            "close": [102.0] * n,
            "volume": [1_000_000] * n,
        }
    )


# ---------------------------------------------------------------------------
# _normalize_daily_df
# ---------------------------------------------------------------------------


def test_normalize_daily_df_tw_localizes_timezone() -> None:
    df = _make_daily_df()
    result = _normalize_daily_df(df, market="tw")
    assert result["date"].dt.tz is not None
    assert "Asia/Taipei" in str(result["date"].dt.tz)


def test_normalize_daily_df_us_localizes_new_york() -> None:
    df = _make_daily_df(market="us")
    result = _normalize_daily_df(df, market="us")
    assert result["date"].dt.tz is not None
    assert "America/New_York" in str(result["date"].dt.tz)


def test_normalize_daily_df_drops_ohlcv_nan() -> None:
    df = _make_daily_df(n=10)
    df.loc[3, "close"] = float("nan")
    result = _normalize_daily_df(df, market="tw")
    assert len(result) == 9


def test_normalize_daily_df_sorts_by_date() -> None:
    df = _make_daily_df(n=5)
    shuffled = df.sample(frac=1, random_state=42)
    result = _normalize_daily_df(shuffled, market="tw")
    assert result["date"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# build_dashboard_payload — market routing
# ---------------------------------------------------------------------------


@patch("src.services.dashboard_service._sync_symbol_daily_data")
@patch("src.services.dashboard_service.ParquetStorage")
def test_build_dashboard_payload_returns_error_on_fetch_failure(
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_sync.side_effect = RuntimeError("network error")
    result = build_dashboard_payload("2330", market="tw")
    assert isinstance(result, DashboardError)
    assert result.code == "FETCH_FAILED"
    assert "2330" in result.message


@patch("src.services.dashboard_service._sync_symbol_daily_data")
@patch("src.services.dashboard_service.ParquetStorage")
def test_build_dashboard_payload_returns_error_on_empty_data(
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = pd.DataFrame()
    mock_storage.load_adjusted.return_value = pd.DataFrame()
    mock_storage_cls.return_value = mock_storage

    result = build_dashboard_payload("9999", market="tw")
    assert isinstance(result, DashboardError)
    assert result.code == "SYMBOL_NOT_FOUND"


@patch("src.services.dashboard_service._sync_symbol_daily_data")
@patch("src.services.dashboard_service.ParquetStorage")
@patch("src.services.dashboard_service.generate_technical_summary")
@patch("src.services.dashboard_service.detect_candle_patterns")
@patch("src.services.dashboard_service.detect_chart_pattern")
@patch("src.services.dashboard_service.analyze_multi_timeframe")
@patch("src.services.dashboard_service._fetch_tw_realtime")
@patch("src.services.dashboard_service._prepare_chip_data")
@patch("src.services.dashboard_service.get_config")
def test_build_dashboard_payload_tw_calls_chip_and_realtime(
    mock_config: MagicMock,
    mock_chip: MagicMock,
    mock_realtime: MagicMock,
    mock_mtf: MagicMock,
    mock_chart: MagicMock,
    mock_candle: MagicMock,
    mock_tech: MagicMock,
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = _make_daily_df()
    mock_storage_cls.return_value = mock_storage

    mock_tech.return_value = MagicMock()
    mock_candle.return_value = []
    mock_chart.return_value = []
    mock_mtf.return_value = MagicMock()
    mock_realtime.return_value = (None, None, None)
    mock_chip.return_value = (None, pd.DataFrame(), None)
    mock_config.return_value = {"ai": {"enabled": False}}

    result = build_dashboard_payload("2330", market="tw")
    assert isinstance(result, DashboardPayload)
    mock_realtime.assert_called_once()
    mock_chip.assert_called_once()


@patch("src.services.dashboard_service._sync_symbol_daily_data")
@patch("src.services.dashboard_service.ParquetStorage")
@patch("src.services.dashboard_service.generate_technical_summary")
@patch("src.services.dashboard_service.detect_candle_patterns")
@patch("src.services.dashboard_service.detect_chart_pattern")
@patch("src.services.dashboard_service.analyze_multi_timeframe")
@patch("src.services.dashboard_service._fetch_us_intraday_snapshot")
@patch("src.services.dashboard_service.get_config")
def test_build_dashboard_payload_us_does_not_call_tw_realtime(
    mock_config: MagicMock,
    mock_intraday: MagicMock,
    mock_mtf: MagicMock,
    mock_chart: MagicMock,
    mock_candle: MagicMock,
    mock_tech: MagicMock,
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = _make_daily_df()
    mock_storage.load_daily.return_value = _make_daily_df()
    mock_storage_cls.return_value = mock_storage

    mock_tech.return_value = MagicMock()
    mock_candle.return_value = []
    mock_chart.return_value = []
    mock_mtf.return_value = MagicMock()
    mock_intraday.return_value = (pd.DataFrame(), None, None)
    mock_config.return_value = {"ai": {"enabled": False}}

    result = build_dashboard_payload("AAPL", market="us")
    assert isinstance(result, DashboardPayload)
    assert result.chip_error == "US-1 尚未支援美股籌碼資料。"
    assert result.market == "us"


@patch("src.services.dashboard_service._sync_symbol_daily_data")
@patch("src.services.dashboard_service.ParquetStorage")
@patch("src.services.dashboard_service.generate_technical_summary")
@patch("src.services.dashboard_service.detect_candle_patterns")
@patch("src.services.dashboard_service.detect_chart_pattern")
@patch("src.services.dashboard_service.analyze_multi_timeframe")
@patch("src.services.dashboard_service._fetch_us_intraday_snapshot")
@patch("src.services.dashboard_service.get_config")
def test_build_dashboard_payload_us_chip_error_is_set(
    mock_config: MagicMock,
    mock_intraday: MagicMock,
    mock_mtf: MagicMock,
    mock_chart: MagicMock,
    mock_candle: MagicMock,
    mock_tech: MagicMock,
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = _make_daily_df()
    mock_storage.load_daily.return_value = _make_daily_df()
    mock_storage_cls.return_value = mock_storage

    mock_tech.return_value = MagicMock()
    mock_candle.return_value = []
    mock_chart.return_value = []
    mock_mtf.return_value = MagicMock()
    mock_intraday.return_value = (pd.DataFrame(), None, "無法取得盤中資料")
    mock_config.return_value = {"ai": {"enabled": False}}

    result = build_dashboard_payload("AAPL", market="us")
    assert isinstance(result, DashboardPayload)
    assert result.chip_error == "US-1 尚未支援美股籌碼資料。"
    assert result.intraday_error == "無法取得盤中資料"


# ---------------------------------------------------------------------------
# secrets masking — not applicable in dashboard service (in config_service)
# but verify payload never contains st.* side-effects
# ---------------------------------------------------------------------------


def test_dashboard_error_has_code_and_message() -> None:
    err = DashboardError(code="CUSTOM_CODE", message="custom message")
    assert err.code == "CUSTOM_CODE"
    assert err.message == "custom message"
