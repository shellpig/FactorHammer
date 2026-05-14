"""Tests for backtest_service (Phase 10-A)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.backtest_service import (
    BacktestJobResult,
    BacktestServiceError,
    build_strategy,
    load_backtest_data,
    run_backtest_job,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daily_df(n: int = 60, tz: str = "Asia/Taipei") -> pd.DataFrame:
    dates = pd.date_range("2022-01-03", periods=n, freq="B", tz=tz)
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
# build_strategy
# ---------------------------------------------------------------------------


def test_build_strategy_ma_cross_returns_strategy() -> None:
    strategy = build_strategy("moving_average_cross", {"short_window": 5, "long_window": 20})
    assert not isinstance(strategy, BacktestServiceError)


def test_build_strategy_ma_cross_rejects_invalid_params() -> None:
    result = build_strategy("moving_average_cross", {"short_window": 60, "long_window": 20})
    assert isinstance(result, BacktestServiceError)
    assert result.code == "INVALID_PARAMS"


def test_build_strategy_rsi_returns_strategy() -> None:
    strategy = build_strategy("rsi", {"period": 14, "oversold": 30, "overbought": 70})
    assert not isinstance(strategy, BacktestServiceError)


def test_build_strategy_unsupported_type_returns_error() -> None:
    result = build_strategy("unknown_strategy_xyz", {})
    assert isinstance(result, BacktestServiceError)
    assert result.code == "UNSUPPORTED_STRATEGY"


def test_build_strategy_kd_cross_returns_strategy() -> None:
    result = build_strategy("kd_cross", {"k_period": 9, "d_period": 3, "smooth_k": 3})
    assert not isinstance(result, BacktestServiceError)


def test_build_strategy_macd_cross_returns_strategy() -> None:
    result = build_strategy("macd_cross", {"fast": 12, "slow": 26, "signal": 9})
    assert not isinstance(result, BacktestServiceError)


def test_build_strategy_bollinger_returns_strategy() -> None:
    result = build_strategy("bollinger_band", {"period": 20, "std_dev": 2.0})
    assert not isinstance(result, BacktestServiceError)


def test_build_strategy_bias_returns_strategy() -> None:
    result = build_strategy("bias", {"ma_period": 20, "buy_bias": -10.0, "sell_bias": 10.0})
    assert not isinstance(result, BacktestServiceError)


def test_build_strategy_donchian_returns_strategy() -> None:
    result = build_strategy("donchian_breakout", {"entry_period": 20, "exit_period": 10})
    assert not isinstance(result, BacktestServiceError)


# ---------------------------------------------------------------------------
# load_backtest_data
# ---------------------------------------------------------------------------


@patch("src.services.backtest_service._sync_symbol_daily_data")
@patch("src.services.backtest_service.ParquetStorage")
def test_load_backtest_data_returns_filtered_dataframe(
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    df = _make_daily_df(n=60)
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = df
    mock_storage_cls.return_value = mock_storage

    start = pd.Timestamp("2022-01-03", tz="Asia/Taipei")
    end = pd.Timestamp("2022-04-01", tz="Asia/Taipei")
    result = load_backtest_data("2330", start, end, market="tw")
    assert isinstance(result, pd.DataFrame)
    assert not result.empty


@patch("src.services.backtest_service._sync_symbol_daily_data")
@patch("src.services.backtest_service.ParquetStorage")
def test_load_backtest_data_returns_error_on_no_adjusted(
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = pd.DataFrame()
    mock_storage_cls.return_value = mock_storage

    start = pd.Timestamp("2022-01-03", tz="Asia/Taipei")
    end = pd.Timestamp("2022-04-01", tz="Asia/Taipei")
    result = load_backtest_data("2330", start, end, market="tw", require_adjusted=True)
    assert isinstance(result, BacktestServiceError)
    assert result.code == "NO_ADJUSTED_DATA"


@patch("src.services.backtest_service._sync_symbol_daily_data")
@patch("src.services.backtest_service.ParquetStorage")
def test_load_backtest_data_us_uses_america_new_york_timezone(
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    df = _make_daily_df(n=60, tz="America/New_York")
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = df
    mock_storage_cls.return_value = mock_storage

    start = pd.Timestamp("2022-01-03", tz="America/New_York")
    end = pd.Timestamp("2022-04-01", tz="America/New_York")
    result = load_backtest_data("AAPL", start, end, market="us")
    assert isinstance(result, pd.DataFrame)
    assert "America/New_York" in str(result["date"].dt.tz)


# ---------------------------------------------------------------------------
# run_backtest_job — market routing and USD caption
# ---------------------------------------------------------------------------


@patch("src.services.backtest_service._sync_symbol_daily_data")
@patch("src.services.backtest_service.ParquetStorage")
@patch("src.services.backtest_service.VectorizedBacktester")
def test_run_backtest_job_us_sets_usd_currency(
    mock_backtester_cls: MagicMock,
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    df = _make_daily_df(n=120, tz="America/New_York")
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = df
    mock_storage_cls.return_value = mock_storage

    mock_engine = MagicMock()
    mock_engine.run.return_value = MagicMock(
        total_trades=5, total_return=0.1, annual_return=0.08,
        max_drawdown=0.05, sharpe_ratio=1.2,
        trades=pd.DataFrame(), signals=None,
    )
    mock_backtester_cls.return_value = mock_engine

    start = pd.Timestamp("2022-01-03", tz="America/New_York")
    end = pd.Timestamp("2022-06-01", tz="America/New_York")
    result = run_backtest_job(
        symbol="AAPL",
        start_ts=start,
        end_exclusive=end,
        strategy_preset={"type": "moving_average_cross", "params": {"short_window": 5, "long_window": 20}},
        market="us",
    )
    assert isinstance(result, BacktestJobResult)
    assert result.currency == "USD"


@patch("src.services.backtest_service._sync_symbol_daily_data")
@patch("src.services.backtest_service.ParquetStorage")
@patch("src.services.backtest_service.VectorizedBacktester")
def test_run_backtest_job_tw_sets_twd_currency(
    mock_backtester_cls: MagicMock,
    mock_storage_cls: MagicMock,
    mock_sync: MagicMock,
) -> None:
    df = _make_daily_df(n=120, tz="Asia/Taipei")
    mock_storage = MagicMock()
    mock_storage.load_adjusted.return_value = df
    mock_storage_cls.return_value = mock_storage

    mock_engine = MagicMock()
    mock_engine.run.return_value = MagicMock(
        total_trades=3, total_return=0.05, annual_return=0.04,
        max_drawdown=0.03, sharpe_ratio=0.9,
        trades=pd.DataFrame(), signals=None,
    )
    mock_backtester_cls.return_value = mock_engine

    start = pd.Timestamp("2022-01-03", tz="Asia/Taipei")
    end = pd.Timestamp("2022-06-01", tz="Asia/Taipei")
    result = run_backtest_job(
        symbol="2330",
        start_ts=start,
        end_exclusive=end,
        strategy_preset={"type": "moving_average_cross", "params": {"short_window": 5, "long_window": 20}},
        market="tw",
    )
    assert isinstance(result, BacktestJobResult)
    assert result.currency == "TWD"


def test_run_backtest_job_returns_error_for_unsupported_strategy() -> None:
    start = pd.Timestamp("2022-01-03", tz="Asia/Taipei")
    end = pd.Timestamp("2022-06-01", tz="Asia/Taipei")

    with patch("src.services.backtest_service._sync_symbol_daily_data"), \
         patch("src.services.backtest_service.ParquetStorage") as mock_storage_cls:
        mock_storage = MagicMock()
        mock_storage.load_adjusted.return_value = _make_daily_df(n=120)
        mock_storage_cls.return_value = mock_storage

        result = run_backtest_job(
            symbol="2330",
            start_ts=start,
            end_exclusive=end,
            strategy_preset={"type": "not_a_real_strategy", "params": {}},
            market="tw",
        )

    assert isinstance(result, BacktestServiceError)
    assert result.code == "UNSUPPORTED_STRATEGY"
