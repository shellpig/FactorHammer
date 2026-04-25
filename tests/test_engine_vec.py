from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtest.engine_vec import VectorizedBacktester
from src.strategy.examples.ma_cross import MACrossStrategy


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ma_cross_data.csv"


def _load_fixture() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def test_ma_cross_signal_golden_cross() -> None:
    df = _load_fixture()
    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    signal = strategy.generate_signals(df)

    known_golden_cross_date = pd.Timestamp("2024-04-01")
    assert signal.loc[known_golden_cross_date] == 1


def test_ma_cross_signal_no_lookahead() -> None:
    df = _load_fixture()
    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    full_signal = strategy.generate_signals(df)

    for i in range(len(df)):
        partial_signal = strategy.generate_signals(df.iloc[: i + 1])
        assert partial_signal.iloc[-1] == full_signal.iloc[i]


def test_ma_cross_signal_alignment() -> None:
    df = _load_fixture()
    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    signal = strategy.generate_signals(df)

    assert signal.index.equals(df.index)
    assert len(signal) == len(df)


def test_signal_values_only_minus1_0_plus1() -> None:
    df = _load_fixture()
    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    signal = strategy.generate_signals(df)

    assert not signal.isna().any()
    assert set(signal.unique().tolist()).issubset({-1, 0, 1})


def test_vectorized_backtest_basic() -> None:
    df = _load_fixture()
    strategy = MACrossStrategy(ma_short=20, ma_long=60)
    backtester = VectorizedBacktester(initial_capital=1_000_000)

    result = backtester.run(strategy, df)

    assert result.total_trades > 0
    assert len(result.equity_curve) == len(df)
