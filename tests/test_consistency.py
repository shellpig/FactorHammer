from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.backtest.cost import CostCalculator
from src.backtest.engine_event import EventDrivenBacktester
from src.backtest.engine_vec import VectorizedBacktester
from src.strategy.examples.ma_cross import MACrossStrategy


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "consistency_data.csv"
INITIAL_CAPITAL = 1_000_000.0
MAX_TOTAL_RETURN_DIFF = 0.01  # 1%


def _load_consistency_data() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _run_both_engines() -> tuple:
    data = _load_consistency_data()
    cost = CostCalculator(
        commission_rate=0.0,
        commission_discount=1.0,
        tax_rate=0.0,
        etf_tax_rate=0.0,
        slippage_ticks=0,
    )
    vec_result = VectorizedBacktester(initial_capital=INITIAL_CAPITAL, cost_calculator=cost).run(
        MACrossStrategy(ma_short=20, ma_long=60),
        data,
    )
    event_result = EventDrivenBacktester(initial_capital=INITIAL_CAPITAL, cost_calculator=cost).run(
        MACrossStrategy(ma_short=20, ma_long=60),
        data,
    )
    return vec_result, event_result


def _entry_date_set(result) -> set:
    if result.trades.empty or "entry_date" not in result.trades.columns:
        return set()
    values = pd.to_datetime(result.trades["entry_date"], errors="coerce").dt.date.dropna().tolist()
    return set(values)


def test_total_return_consistency() -> None:
    vec_result, event_result = _run_both_engines()
    diff = abs(float(vec_result.total_return) - float(event_result.total_return))

    assert diff < MAX_TOTAL_RETURN_DIFF, (
        "Total return deviation exceeds 1%. "
        f"vectorized={vec_result.total_return:.6f}, "
        f"event_driven={event_result.total_return:.6f}, diff={diff:.6f}"
    )


def test_trade_count_consistency() -> None:
    vec_result, event_result = _run_both_engines()

    assert vec_result.total_trades == event_result.total_trades


def test_entry_dates_consistency() -> None:
    vec_result, event_result = _run_both_engines()
    vec_entries = _entry_date_set(vec_result)
    event_entries = _entry_date_set(event_result)

    assert vec_entries, "Vectorized engine produced no entry dates in consistency fixture."
    assert vec_entries == event_entries


def test_deviation_report() -> None:
    vec_result, event_result = _run_both_engines()
    diff = abs(float(vec_result.total_return) - float(event_result.total_return))

    if diff < MAX_TOTAL_RETURN_DIFF:
        return

    vec_trades = vec_result.trades.copy(deep=True)
    event_trades = event_result.trades.copy(deep=True)
    vec_trades["entry_date"] = pd.to_datetime(vec_trades.get("entry_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    vec_trades["exit_date"] = pd.to_datetime(vec_trades.get("exit_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    event_trades["entry_date"] = pd.to_datetime(event_trades.get("entry_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    event_trades["exit_date"] = pd.to_datetime(event_trades.get("exit_date"), errors="coerce").dt.strftime("%Y-%m-%d")

    columns = ["entry_date", "exit_date", "quantity", "entry_price", "exit_price", "pnl"]
    vec_preview = vec_trades.reindex(columns=columns).head(5).to_string(index=False)
    event_preview = event_trades.reindex(columns=columns).head(5).to_string(index=False)
    report = (
        "Consistency deviation report\n"
        f"vectorized total_return={vec_result.total_return:.6f}\n"
        f"event_driven total_return={event_result.total_return:.6f}\n"
        f"diff={diff:.6f} (threshold={MAX_TOTAL_RETURN_DIFF:.6f})\n"
        f"vectorized total_trades={vec_result.total_trades}, event_driven total_trades={event_result.total_trades}\n"
        "Possible causes: fill-price/slippage assumption mismatch, quantity rounding mismatch.\n"
        "Vectorized first 5 trades:\n"
        f"{vec_preview}\n"
        "Event-driven first 5 trades:\n"
        f"{event_preview}"
    )
    pytest.fail(report)
