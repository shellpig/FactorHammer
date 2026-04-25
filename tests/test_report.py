from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtest.metrics import BacktestResult, calculate_metrics
from src.backtest.report import TearsheetReport


def make_mock_result(all_winning: bool = False) -> BacktestResult:
    dates = pd.bdate_range("2024-01-02", periods=80)
    if all_winning:
        equity = pd.Series([1_000_000 + i * 1500 for i in range(len(dates))], index=dates, dtype="float64")
        trades = pd.DataFrame(
            {
                "entry_date": pd.to_datetime(["2024-01-03", "2024-02-01"]),
                "exit_date": pd.to_datetime(["2024-01-10", "2024-02-09"]),
                "side": ["LONG", "LONG"],
                "pnl": [12000.0, 8000.0],
            }
        )
    else:
        base = [1_000_000 + i * 800 for i in range(len(dates))]
        for i in range(15, len(base), 20):
            base[i] -= 18_000
        equity = pd.Series(base, index=dates, dtype="float64")
        trades = pd.DataFrame(
            {
                "entry_date": pd.to_datetime(["2024-01-05", "2024-02-12", "2024-03-18"]),
                "exit_date": pd.to_datetime(["2024-01-15", "2024-02-26", "2024-03-29"]),
                "side": ["LONG", "LONG", "LONG"],
                "pnl": [10_000.0, -6_000.0, 4_000.0],
            }
        )
    return calculate_metrics(equity_curve=equity, trades=trades)


def test_tearsheet_renders_without_error() -> None:
    result = make_mock_result(all_winning=True)
    report = TearsheetReport(result)

    fig = report.create_full_tearsheet()
    assert len(fig.data) >= 4

    summary = report.create_summary_table()
    summary_values = list(summary.data[0]["cells"]["values"][1])
    assert "N/A" in summary_values


def test_tearsheet_save_html() -> None:
    result = make_mock_result()
    report = TearsheetReport(result)

    out = Path("data/backtest/test_tearsheet_unit.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(out))

    assert out.exists()
    assert out.stat().st_size > 0
