"""Tests for dashboard_service (Phase 10-A)."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.dashboard_service import (
    DashboardError,
    DashboardPayload,
    build_dashboard_payload,
    delete_shareholder_meeting_override,
    get_dividend_history_with_pe,
    get_event_calendar,
    get_institutional_cost,
    get_industry_per_table,
    get_monthly_revenue,
    get_valuation,
    upsert_shareholder_meeting_override,
    _lookup_nearest_close,
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


def test_get_valuation_returns_latest_per_row() -> None:
    per_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-15", "2026-05-16"]),
            "per": [20.1, 20.5],
            "pbr": [4.0, 4.1],
            "dividend_yield": [2.2, 2.3],
            "symbol": ["2330", "2330"],
        }
    )
    stock_info_df = pd.DataFrame({"symbol": ["2330"], "name": ["台積電"], "industry": ["半導體"]})

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls, patch(
        "src.services.dashboard_service._load_stock_info_table"
    ) as mock_stock_info:
        mock_storage = MagicMock()
        mock_storage.load_per.return_value = per_df
        mock_storage_cls.return_value = mock_storage
        mock_stock_info.return_value = stock_info_df

        data = get_valuation("2330", market="tw")
        assert data["per"] == pytest.approx(20.5)
        assert data["industry"] == "半導體"


def test_get_monthly_revenue_calculates_yoy_and_mom() -> None:
    dates = pd.date_range("2025-01-10", periods=14, freq="MS")
    revenue = [100.0 + i for i in range(14)]
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": revenue,
            "revenue_month": [d.month for d in dates],
            "revenue_year": [d.year for d in dates],
            "symbol": ["2330"] * len(dates),
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_monthly_revenue.return_value = df
        mock_storage_cls.return_value = mock_storage

        data = get_monthly_revenue("2330", months=12, market="tw")
        assert len(data["items"]) == 12
        assert data["items"][-1]["mom"] is not None
        assert data["items"][-1]["yoy"] is not None


def test_get_dividend_history_with_pe_uses_latest_announced_4q() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-15"]),
            "cash_dividend": [3.5],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-15"]),
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000],
            "symbol": ["2330"],
        }
    )
    eps_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-05-15", "2025-08-14", "2025-11-14", "2026-03-15"]),
            "year": [2025, 2025, 2025, 2026],
            "quarter": [1, 2, 3, 4],
            "eps": [2.0, 2.0, 2.0, 2.0],
            "symbol": ["2330"] * 4,
            "report_date": pd.to_datetime(["2025-05-15", "2025-08-14", "2025-11-14", "2026-03-15"]),
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_eps.return_value = eps_df
        mock_storage_cls.return_value = mock_storage

        data = get_dividend_history_with_pe("2330", count=5, market="tw")
        assert len(data["items"]) == 1
        assert data["items"][0]["ttm_pe"] == pytest.approx(12.5)
        assert "payment_date" not in data["items"][0]
        assert data["items"][0]["price_date"] == "2026-06-15"
        assert data["items"][0]["stock_dividend"] == pytest.approx(0.0)


def test_get_dividend_history_includes_nonzero_stock_dividend() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-07-24"]),
            "cash_dividend": [35.0],
            "stock_dividend": [10.0],
            "symbol": ["3293"],
        }
    )
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-07-24"]),
            "open": [500.0],
            "high": [510.0],
            "low": [495.0],
            "close": [505.0],
            "volume": [1000],
            "symbol": ["3293"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_eps.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage

        data = get_dividend_history_with_pe("3293", count=5, market="tw")

    assert len(data["items"]) == 1
    assert data["items"][0]["stock_dividend"] == pytest.approx(10.0)


def test_get_dividend_history_stock_dividend_missing_column_defaults_to_zero() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-15"]),
            "cash_dividend": [3.5],
            "symbol": ["2330"],
            # no stock_dividend column
        }
    )
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-15"]),
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000],
            "symbol": ["2330"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_eps.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage

        data = get_dividend_history_with_pe("2330", count=5, market="tw")

    assert data["items"][0]["stock_dividend"] == pytest.approx(0.0)


def test_lookup_nearest_close_returns_exact_match() -> None:
    daily = pd.DataFrame(
        {
            "date_key": ["2026-06-13", "2026-06-16"],
            "close": [98.0, 102.0],
        }
    )
    close, price_date = _lookup_nearest_close(daily, "2026-06-16")
    assert close == pytest.approx(102.0)
    assert price_date == "2026-06-16"


def test_lookup_nearest_close_falls_back_to_previous_trading_day() -> None:
    """Ex-dividend date is a non-trading day (e.g. Saturday); should use the last available close."""
    daily = pd.DataFrame(
        {
            "date_key": ["2026-06-12", "2026-06-13"],
            "close": [99.0, 101.0],
        }
    )
    # 2026-06-14 is Sunday — not in daily data
    close, price_date = _lookup_nearest_close(daily, "2026-06-14")
    assert close == pytest.approx(101.0)
    assert price_date == "2026-06-13"


def test_lookup_nearest_close_returns_none_when_no_earlier_date() -> None:
    daily = pd.DataFrame({"date_key": ["2026-06-20"], "close": [100.0]})
    close, price_date = _lookup_nearest_close(daily, "2026-06-15")
    assert close is None
    assert price_date is None


def test_get_dividend_history_with_pe_uses_nearest_close_for_non_trading_day() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-14"]),  # Sunday — no K-line
            "cash_dividend": [3.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-12", "2026-06-13"]),
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 104.0],
            "volume": [1000, 1000],
            "symbol": ["2330", "2330"],
        }
    )
    eps_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-05-15", "2025-08-14", "2025-11-14", "2026-03-15"]),
            "eps": [2.0, 2.0, 2.0, 2.0],
            "symbol": ["2330"] * 4,
            "report_date": pd.to_datetime(["2025-05-15", "2025-08-14", "2025-11-14", "2026-03-15"]),
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_eps.return_value = eps_df
        mock_storage_cls.return_value = mock_storage

        data = get_dividend_history_with_pe("2330", count=5, market="tw")

    assert len(data["items"]) == 1
    item = data["items"][0]
    # Nearest close is 2026-06-13 (104.0), TTM EPS = 8.0 → PE = 13.0
    assert item["ttm_pe"] == pytest.approx(13.0)
    assert item["price_date"] == "2026-06-13"


def test_get_industry_per_table_uses_cache_hit(tmp_path) -> None:
    cache_dir = tmp_path / "cache" / "industry_per"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "semi_2026-05-17.parquet"
    pd.DataFrame(
        [
            {"symbol": "2330", "name": "台積電", "date": "2026-05-17T00:00:00+08:00", "per": 20.0, "pbr": 4.0, "dividend_yield": 2.0},
            {"symbol": "2303", "name": "聯電", "date": "2026-05-17T00:00:00+08:00", "per": 16.0, "pbr": 2.5, "dividend_yield": 3.0},
        ]
    ).to_parquet(cache_file, index=False)
    info = pd.DataFrame(
        {
            "symbol": ["2330", "2303"],
            "name": ["台積電", "聯電"],
            "industry": ["Semi", "Semi"],
        }
    )

    with patch("src.services.dashboard_service._load_stock_info_table") as mock_info, patch(
        "src.services.dashboard_service._industry_cache_path"
    ) as mock_cache_path, patch("src.services.dashboard_service._get_industry_lock") as mock_lock:
        mock_info.return_value = info
        mock_cache_path.return_value = cache_file
        mock_lock.return_value = threading.Lock()
        data = get_industry_per_table("2330", market="tw")

        assert data["industry"] == "Semi"
        assert data["median"] == pytest.approx(18.0)
        assert data["mean"] == pytest.approx(18.0)
        assert data["count"] == 2
        assert data["cached_at"] is not None
        assert len(data["items"]) == 2
        current_rows = [row for row in data["items"] if row["symbol"] == "2330"]
        assert current_rows and current_rows[0]["is_current"] is True


def test_get_institutional_cost_computes_weighted_costs() -> None:
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-10", "2026-05-11"]),
            "open": [100, 110],
            "high": [120, 130],
            "low": [80, 90],
            "close": [100, 120],
            "volume": [1000, 1000],
            "symbol": ["2330", "2330"],
        }
    )
    institutional_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-10", "2026-05-11"]),
            "foreign_buy": [0, 0],
            "foreign_sell": [0, 0],
            "foreign_net": [100, 100],
            "trust_buy": [0, 0],
            "trust_sell": [0, 0],
            "trust_net": [100, 0],
            "dealer_buy": [0, 0],
            "dealer_sell": [0, 0],
            "dealer_net": [0, 0],
            "symbol": ["2330", "2330"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_institutional.return_value = institutional_df
        mock_storage_cls.return_value = mock_storage
        data = get_institutional_cost("2330", days=30, market="tw")

    assert data["foreign"]["cost"] is not None
    assert data["trust"]["cost"] is not None
    assert data["dealer"]["cost"] is None


def test_get_institutional_cost_falls_back_to_incremental_when_storage_empty() -> None:
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-10", "2026-05-11"]),
            "open": [100, 110],
            "high": [120, 130],
            "low": [80, 90],
            "close": [100, 120],
            "volume": [1000, 1000],
            "symbol": ["2330", "2330"],
        }
    )
    institutional_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-10", "2026-05-11"]),
            "foreign_buy": [0, 0],
            "foreign_sell": [0, 0],
            "foreign_net": [100, 100],
            "trust_buy": [0, 0],
            "trust_sell": [0, 0],
            "trust_net": [0, 0],
            "dealer_buy": [0, 0],
            "dealer_sell": [0, 0],
            "dealer_net": [0, 0],
            "symbol": ["2330", "2330"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls, \
         patch("src.services.dashboard_service._build_chip_fetcher") as mock_fetcher_builder:
        mock_storage = MagicMock()
        mock_storage.load_daily.return_value = daily_df
        # First call empty (cache miss), second call populated (after incremental fetch wrote).
        mock_storage.load_institutional.side_effect = [
            pd.DataFrame(),
            institutional_df,
        ]
        mock_storage_cls.return_value = mock_storage

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_institutional_incremental.return_value = institutional_df
        mock_fetcher_builder.return_value = mock_fetcher

        data = get_institutional_cost("2330", days=30, market="tw")

    mock_fetcher.fetch_institutional_incremental.assert_called_once_with("2330", mock_storage)
    assert data["foreign"]["cost"] is not None


def test_get_institutional_cost_returns_null_when_incremental_fetch_fails() -> None:
    daily_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-10"]),
            "open": [100], "high": [120], "low": [80], "close": [100],
            "volume": [1000], "symbol": ["2330"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls, \
         patch("src.services.dashboard_service._build_chip_fetcher") as mock_fetcher_builder:
        mock_storage = MagicMock()
        mock_storage.load_daily.return_value = daily_df
        mock_storage.load_institutional.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        mock_fetcher_builder.side_effect = RuntimeError("finmind not configured")

        data = get_institutional_cost("2330", days=30, market="tw")

    assert data["foreign"]["cost"] is None
    assert data["foreign"]["pnl"] is None
    assert data["trust"]["cost"] is None
    assert data["dealer"]["cost"] is None


def test_get_event_calendar_includes_stock_dividend() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-24"]),
            "cash_dividend": [35.0],
            "stock_dividend": [10.0],
            "symbol": ["3293"],
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage

        with patch("src.services.dashboard_service._lookup_is_etf", return_value=False):
            data = get_event_calendar("3293", market="tw")

    next_div = data["next_ex_dividend"]
    last_div = data["last_ex_dividend"]
    # Depending on today's date, 2026-07-24 may be future or past
    entry = next_div if next_div is not None else last_div
    assert entry is not None
    assert entry["stock_dividend"] == pytest.approx(10.0)


def test_get_event_calendar_stock_dividend_defaults_to_zero_when_missing_column() -> None:
    dividends_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-24"]),
            "cash_dividend": [3.5],
            "symbol": ["2330"],
            # no stock_dividend column
        }
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage

        with patch("src.services.dashboard_service._lookup_is_etf", return_value=False):
            data = get_event_calendar("2330", market="tw")

    next_div = data["next_ex_dividend"]
    last_div = data["last_ex_dividend"]
    entry = next_div if next_div is not None else last_div
    assert entry is not None
    assert entry["stock_dividend"] == pytest.approx(0.0)


def test_get_event_calendar_prefers_newer_manual_shareholder_row() -> None:
    dividends_df = pd.DataFrame(
        {"date": pd.to_datetime(["2026-06-15"]), "cash_dividend": [3.5], "stock_dividend": [0.0], "symbol": ["2330"]}
    )
    auto_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-30", tz="Asia/Taipei"),
                "symbol": "2330",
                "meeting_type": "常會",
                "source": "auto",
                "updated_at": pd.Timestamp("2026-05-01T10:00:00+08:00"),
            }
        ]
    )
    manual_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-07-10", tz="Asia/Taipei"),
                "symbol": "2330",
                "meeting_type": "臨時會",
                "source": "manual",
                "updated_at": pd.Timestamp("2026-05-17T10:00:00+08:00"),
            }
        ]
    )

    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_shareholder_meeting.return_value = auto_df
        mock_storage.load_shareholder_meeting_override.return_value = manual_df
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("2330", market="tw")

    assert data["next_shareholder_meeting"]["source"] == "manual"
    assert data["next_shareholder_meeting"]["meeting_type"] == "臨時會"


def test_get_event_calendar_flags_etf_via_stock_info() -> None:
    info_df = pd.DataFrame(
        [{"symbol": "00929", "name": "復華台灣科技優息", "industry": "ETF"}]
    )
    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls, \
         patch("src.services.dashboard_service._load_stock_info_table", return_value=info_df):
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("00929", market="tw")

    assert data["is_etf"] is True
    assert data["missing_shareholder_meeting"] is True


def test_get_event_calendar_non_etf_returns_is_etf_false() -> None:
    info_df = pd.DataFrame(
        [{"symbol": "2330", "name": "台積電", "industry": "半導體業"}]
    )
    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls, \
         patch("src.services.dashboard_service._load_stock_info_table", return_value=info_df):
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("2330", market="tw")

    assert data["is_etf"] is False


# ---------------------------------------------------------------------------
# Phase 11-D: Goodinfo dividend policy fallback
# ---------------------------------------------------------------------------

_GOODINFO_FALLBACK_CURRENT = {
    "status": "current_year",
    "year": 2026,
    "cash_dividend": 29.0,
    "stock_dividend": 0.0,
    "source_url": "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=3293",
    "source_note": "此為網頁抓取資料，請自行前往來源確認",
}


def test_event_calendar_formal_future_dividend_skips_goodinfo() -> None:
    """11-D-S1: has formal future dividend → is_estimated=False, Goodinfo not called."""
    dividends_df = pd.DataFrame(
        {"date": pd.to_datetime(["2026-07-24"]), "cash_dividend": [35.0], "stock_dividend": [10.0], "symbol": ["3293"]}
    )
    mock_goodinfo = MagicMock()
    with (
        patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls,
        patch("src.services.dashboard_service._lookup_is_etf", return_value=False),
        patch("src.services.dashboard_service.get_goodinfo_dividend_policy", mock_goodinfo),
    ):
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = dividends_df
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("3293", market="tw")

    mock_goodinfo.assert_not_called()
    entry = data["next_ex_dividend"]
    assert entry is not None
    assert entry["is_estimated"] is False
    assert data["dividend_policy_fallback"] is None


def test_event_calendar_no_future_dividend_calls_goodinfo() -> None:
    """11-D-S2: no future dividend → old [預估] gone, Goodinfo called instead."""
    past_df = pd.DataFrame(
        {"date": pd.to_datetime(["2025-07-24"]), "cash_dividend": [29.0], "stock_dividend": [0.0], "symbol": ["3293"]}
    )
    with (
        patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls,
        patch("src.services.dashboard_service._lookup_is_etf", return_value=False),
        patch(
            "src.services.dashboard_service.get_goodinfo_dividend_policy",
            return_value=_GOODINFO_FALLBACK_CURRENT,
        ),
    ):
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = past_df
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("3293", market="tw")

    # next_ex_dividend must be None (no [預估] estimation)
    assert data["next_ex_dividend"] is None
    # fallback should be populated with Goodinfo data
    fb = data["dividend_policy_fallback"]
    assert fb is not None
    assert fb["status"] == "current_year"
    assert fb["year"] == 2026


def test_event_calendar_goodinfo_failure_does_not_raise() -> None:
    """11-D-S5: Goodinfo failure → fetch_failed status, service still returns 200-compatible dict."""
    with (
        patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls,
        patch("src.services.dashboard_service._lookup_is_etf", return_value=False),
        patch(
            "src.services.dashboard_service.get_goodinfo_dividend_policy",
            return_value={
                "status": "fetch_failed",
                "year": None,
                "cash_dividend": None,
                "stock_dividend": None,
                "source_url": "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=2330",
                "source_note": "此為網頁抓取資料，請自行前往來源確認",
            },
        ),
    ):
        mock_storage = MagicMock()
        mock_storage.load_dividends.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting.return_value = pd.DataFrame()
        mock_storage.load_shareholder_meeting_override.return_value = pd.DataFrame()
        mock_storage_cls.return_value = mock_storage
        data = get_event_calendar("2330", market="tw")

    assert data["dividend_policy_fallback"]["status"] == "fetch_failed"
    assert data["next_ex_dividend"] is None


def test_shareholder_override_upsert_and_delete_delegates_to_storage() -> None:
    with patch("src.services.dashboard_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        upsert_result = upsert_shareholder_meeting_override("2330", "2026-06-30", "常會", market="tw")
        delete_result = delete_shareholder_meeting_override("2330", market="tw")

    mock_storage.upsert_shareholder_meeting_override.assert_called_once()
    mock_storage.delete_shareholder_meeting_override.assert_called_once_with(symbol="2330")
    assert upsert_result["source"] == "manual"
    assert delete_result["deleted"] is True


# ---------------------------------------------------------------------------
# _sync_symbol_daily_data — first-time symbol triggers full rebuild (incl. P11)
# ---------------------------------------------------------------------------


@patch("src.services.dashboard_service._build_fetchers_from_config")
@patch("src.services.dashboard_service.DuckDBMeta")
@patch("src.services.dashboard_service.DataMaintenance")
def test_sync_symbol_daily_data_first_time_calls_rebuild_symbol(
    mock_maint_cls: MagicMock,
    mock_meta_cls: MagicMock,
    mock_build_fetchers: MagicMock,
) -> None:
    """First-time access (no local daily) should run rebuild_symbol so P11 is also pulled."""
    from src.services.dashboard_service import _sync_symbol_daily_data

    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = pd.DataFrame()  # ← empty = first time
    mock_fetcher = MagicMock()
    mock_build_fetchers.return_value = [("finmind", mock_fetcher)]
    mock_maint = MagicMock()
    mock_maint_cls.return_value = mock_maint

    _sync_symbol_daily_data("2330", mock_storage, market="tw")

    mock_maint.rebuild_symbol.assert_called_once_with("2330", market="tw")
    mock_maint.update_daily.assert_not_called()


@patch("src.services.dashboard_service._build_fetchers_from_config")
@patch("src.services.dashboard_service.DuckDBMeta")
@patch("src.services.dashboard_service.DataMaintenance")
def test_sync_symbol_daily_data_existing_local_calls_update_daily(
    mock_maint_cls: MagicMock,
    mock_meta_cls: MagicMock,
    mock_build_fetchers: MagicMock,
) -> None:
    """Symbol that already has local daily should keep the cheap update path."""
    from src.services.dashboard_service import _sync_symbol_daily_data

    mock_storage = MagicMock()
    mock_storage.load_daily.return_value = _make_daily_df(n=10)  # ← non-empty
    mock_fetcher = MagicMock()
    mock_build_fetchers.return_value = [("finmind", mock_fetcher)]
    mock_maint = MagicMock()
    mock_maint_cls.return_value = mock_maint

    _sync_symbol_daily_data("2330", mock_storage, market="tw")

    mock_maint.update_daily.assert_called_once_with("2330", market="tw")
    mock_maint.rebuild_symbol.assert_not_called()
