from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

from src.backtest.cost import CostCalculator
from src.backtest.engine_event import EventDrivenBacktester
from src.backtest.engine_vec import VectorizedBacktester
from src.backtest.events import FillEvent, OrderEvent
from src.strategy.base import StrategyBase
from src.strategy.examples.ma_cross import MACrossStrategy


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ma_cross_data.csv"


def _build_data(rows: int = 8) -> pd.DataFrame:
    index = pd.date_range("2024-01-02 09:00", periods=rows, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0][:rows],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0][:rows],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0][:rows],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5][:rows],
            "volume": [1000] * rows,
            "symbol": ["2330"] * rows,
        },
        index=index,
    )


def _build_consistency_fixture() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=6, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 103.0, 106.0, 107.0, 109.0],
            "high": [101.0, 103.0, 104.0, 107.0, 109.0, 110.0],
            "low": [99.0, 100.0, 102.0, 104.0, 106.0, 108.0],
            "close": [100.0, 102.0, 104.0, 105.0, 108.0, 110.0],
            "symbol": ["2330"] * 6,
        },
        index=index,
    )


def _load_ma_cross_fixture() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _build_ma_cross_event_fixture() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=8, freq="D")
    close = [10.0, 9.0, 8.0, 9.0, 10.0, 9.0, 8.0, 7.0]
    return pd.DataFrame(
        {
            "open": close,
            "high": [x + 0.5 for x in close],
            "low": [x - 0.5 for x in close],
            "close": close,
            "volume": [1000] * len(close),
            "symbol": ["2330"] * len(close),
        },
        index=index,
    )


@dataclass
class CountingStrategy(StrategyBase):
    call_count: int = 0

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(0, index=df.index, dtype="int8")

    def on_bar(self, bar, account) -> list[OrderEvent]:
        _ = (bar, account)
        self.call_count += 1
        return []


@dataclass
class SingleOrderStrategy(StrategyBase):
    trigger_index: int
    side: str = "BUY"
    quantity: int = 1000
    call_index: int = 0
    fills: list[FillEvent] = field(default_factory=list)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(0, index=df.index, dtype="int8")

    def on_bar(self, bar, account) -> list[OrderEvent]:
        _ = account
        orders: list[OrderEvent] = []
        if self.call_index == self.trigger_index:
            orders.append(
                OrderEvent(
                    symbol=bar.symbol,
                    order_type="MARKET",
                    side=self.side,
                    quantity=self.quantity,
                )
            )
        self.call_index += 1
        return orders

    def on_fill(self, fill, account) -> None:
        _ = account
        self.fills.append(fill)


@dataclass
class TwoOrdersStrategy(StrategyBase):
    buy_index: int
    sell_index: int
    call_index: int = 0
    fills: list[FillEvent] = field(default_factory=list)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(0, index=df.index, dtype="int8")

    def on_bar(self, bar, account) -> list[OrderEvent]:
        _ = account
        orders: list[OrderEvent] = []
        if self.call_index == self.buy_index:
            orders.append(OrderEvent(symbol=bar.symbol, order_type="MARKET", side="BUY", quantity=1000))
        if self.call_index == self.sell_index:
            orders.append(OrderEvent(symbol=bar.symbol, order_type="MARKET", side="SELL", quantity=1000))
        self.call_index += 1
        return orders

    def on_fill(self, fill, account) -> None:
        _ = account
        self.fills.append(fill)


@dataclass
class DeterministicVectorStrategy(StrategyBase):
    signals: list[int]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) != len(self.signals):
            raise ValueError("Signal length must match dataframe length.")
        return pd.Series(self.signals, index=df.index, dtype="int8")

    def on_bar(self, bar, account) -> list[OrderEvent]:
        _ = (bar, account)
        return []


@dataclass
class NoFutureStrategy(StrategyBase):
    expected_close: list[float]
    call_index: int = 0
    positions_seen: list[int] = field(default_factory=list)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(0, index=df.index, dtype="int8")

    def on_bar(self, bar, account) -> list[OrderEvent]:
        assert bar.close == pytest.approx(self.expected_close[self.call_index], abs=1e-9)
        self.positions_seen.append(account.get_position(bar.symbol))

        orders: list[OrderEvent] = []
        if self.call_index == 0:
            orders.append(
                OrderEvent(
                    symbol=bar.symbol,
                    order_type="MARKET",
                    side="BUY",
                    quantity=1000,
                )
            )
        self.call_index += 1
        return orders


def test_on_bar_called_per_bar() -> None:
    df = _build_data()
    strategy = CountingStrategy()
    backtester = EventDrivenBacktester(initial_capital=1_000_000)

    backtester.run(strategy, df)

    assert strategy.call_count == len(df)


def test_order_filled_next_bar() -> None:
    df = _build_data()
    strategy = SingleOrderStrategy(trigger_index=2, side="BUY")
    backtester = EventDrivenBacktester(initial_capital=1_000_000)

    backtester.run(strategy, df)

    assert len(strategy.fills) == 1
    assert pd.Timestamp(strategy.fills[0].timestamp) == df.index[3]


def test_market_order_fill_price() -> None:
    df = _build_data()
    calc = CostCalculator(slippage_ticks=1)
    strategy = SingleOrderStrategy(trigger_index=0, side="BUY")
    backtester = EventDrivenBacktester(initial_capital=1_000_000, cost_calculator=calc)

    backtester.run(strategy, df)

    expected = calc.apply_slippage(price=float(df.iloc[1]["open"]), side="BUY")
    assert len(strategy.fills) == 1
    assert strategy.fills[0].fill_price == pytest.approx(expected, abs=1e-9)


def test_market_buy_is_resized_to_affordable_quantity() -> None:
    index = pd.date_range("2025-08-28", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [1160.0, 1180.0, 1190.0],
            "high": [1165.0, 1185.0, 1195.0],
            "low": [1155.0, 1175.0, 1185.0],
            "close": [1160.0, 1180.0, 1190.0],
            "volume": [1000, 1000, 1000],
            "symbol": ["2330", "2330", "2330"],
        },
        index=index,
    )
    initial_capital = 1_000_000.0
    calc = CostCalculator(slippage_ticks=0)
    strategy = SingleOrderStrategy(trigger_index=0, side="BUY", quantity=1000)
    backtester = EventDrivenBacktester(initial_capital=initial_capital, cost_calculator=calc)

    backtester.run(strategy, df)

    assert len(strategy.fills) == 1
    fill = strategy.fills[0]
    assert fill.quantity < 1000

    total_spend = (fill.fill_price * fill.quantity) + fill.commission
    assert total_spend <= initial_capital + 1e-9

    next_qty = fill.quantity + 1
    next_spend = (fill.fill_price * next_qty) + max(
        fill.fill_price * next_qty * calc.effective_commission_rate,
        20.0,
    )
    assert next_spend > initial_capital


def test_no_future_function() -> None:
    df = _build_data()
    strategy = NoFutureStrategy(expected_close=df["close"].tolist())
    backtester = EventDrivenBacktester(initial_capital=1_000_000)

    backtester.run(strategy, df)

    assert strategy.call_index == len(df)
    assert strategy.positions_seen[0] == 0
    assert strategy.positions_seen[1] > 0


def test_equity_curve_length() -> None:
    df = _build_data()
    strategy = CountingStrategy()
    backtester = EventDrivenBacktester(initial_capital=1_000_000)

    result = backtester.run(strategy, df)
    assert len(result.equity_curve) == len(df)


def test_last_bar_pending_orders_discarded() -> None:
    df = _build_data()
    strategy = SingleOrderStrategy(trigger_index=len(df) - 1, side="BUY")
    backtester = EventDrivenBacktester(initial_capital=1_000_000)

    result = backtester.run(strategy, df)

    assert len(strategy.fills) == 0
    assert result.total_trades == 0
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000_000.0, abs=1e-9)


def test_total_trades_counts_round_trips_not_fills() -> None:
    df = _build_data()
    strategy = TwoOrdersStrategy(buy_index=0, sell_index=3)
    backtester = EventDrivenBacktester(initial_capital=1_000_000, cost_calculator=CostCalculator(slippage_ticks=0))

    result = backtester.run(strategy, df)

    assert len(strategy.fills) == 2
    assert result.total_trades == 1
    assert len(result.trades) == 1


def test_round_trip_pnl_matches_hand_calculated() -> None:
    df = _build_data()
    calc = CostCalculator(slippage_ticks=0)
    strategy = TwoOrdersStrategy(buy_index=0, sell_index=3)
    backtester = EventDrivenBacktester(initial_capital=1_000_000, cost_calculator=calc)

    result = backtester.run(strategy, df)

    trade = result.trades.iloc[0]
    assert pd.Timestamp(trade["entry_date"]) == df.index[1]
    assert pd.Timestamp(trade["exit_date"]) == df.index[4]
    assert float(trade["entry_price"]) == pytest.approx(101.0, abs=1e-9)
    assert float(trade["exit_price"]) == pytest.approx(104.0, abs=1e-9)

    buy_commission = max(101_000 * 0.001425 * 0.6, 20.0)
    sell_commission = max(104_000 * 0.001425 * 0.6, 20.0)
    sell_tax = 104_000 * 0.003
    expected_pnl = (104_000 - sell_commission - sell_tax) - (101_000 + buy_commission)
    assert float(trade["pnl"]) == pytest.approx(expected_pnl, abs=1e-6)


def test_event_engine_matches_vectorized() -> None:
    df = _build_consistency_fixture()
    calc = CostCalculator(slippage_ticks=0)
    initial_capital = 150_000.0

    vec_result = VectorizedBacktester(initial_capital=initial_capital, cost_calculator=calc).run(
        DeterministicVectorStrategy(signals=[1, 0, 0, -1, 0, 0]),
        df,
    )
    event_result = EventDrivenBacktester(initial_capital=initial_capital, cost_calculator=calc).run(
        TwoOrdersStrategy(buy_index=0, sell_index=3),
        df,
    )

    assert vec_result.total_trades == event_result.total_trades
    assert vec_result.total_return == pytest.approx(event_result.total_return, abs=1e-6)

    vec_trade = vec_result.trades.iloc[0]
    event_trade = event_result.trades.iloc[0]
    assert pd.Timestamp(vec_trade["entry_date"]).date() == pd.Timestamp(event_trade["entry_date"]).date()
    assert pd.Timestamp(vec_trade["exit_date"]).date() == pd.Timestamp(event_trade["exit_date"]).date()
    assert float(vec_trade["pnl"]) == pytest.approx(float(event_trade["pnl"]), abs=1e-6)


def test_strategy_abc_enforcement() -> None:
    class IncompleteStrategy(StrategyBase):
        def generate_signals(self, df: pd.DataFrame) -> pd.Series:
            return pd.Series(0, index=df.index, dtype="int8")

    with pytest.raises(TypeError):
        IncompleteStrategy()


def test_ma_cross_event_same_entry_points() -> None:
    df = _build_ma_cross_event_fixture()
    calc = CostCalculator(slippage_ticks=0)

    vec_result = VectorizedBacktester(initial_capital=1_000_000, cost_calculator=calc).run(
        MACrossStrategy(ma_short=2, ma_long=3),
        df,
    )
    event_result = EventDrivenBacktester(initial_capital=1_000_000, cost_calculator=calc).run(
        MACrossStrategy(ma_short=2, ma_long=3),
        df,
    )

    vec_entry_dates = [pd.Timestamp(x).date() for x in vec_result.trades["entry_date"].tolist()]
    event_entry_dates = [pd.Timestamp(x).date() for x in event_result.trades["entry_date"].tolist()]
    vec_exit_dates = [pd.Timestamp(x).date() for x in vec_result.trades["exit_date"].tolist()]
    event_exit_dates = [pd.Timestamp(x).date() for x in event_result.trades["exit_date"].tolist()]

    assert vec_entry_dates == event_entry_dates
    assert vec_exit_dates == event_exit_dates


def test_infer_freq_daily() -> None:
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    tz = "Asia/Taipei"
    idx = pd.date_range("2024-01-01", periods=5, freq="B", tz=tz)
    assert bt._infer_freq(idx) == "1day"


def test_infer_freq_too_short_returns_1day() -> None:
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    tz = "Asia/Taipei"
    idx = pd.date_range("2024-01-01", periods=2, freq="1min", tz=tz)
    assert bt._infer_freq(idx) == "1day"


def test_infer_freq_minute_old_alias() -> None:
    """pd.infer_freq returns 'T'/'5T' on older pandas — simulate via DatetimeIndex."""
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    tz = "Asia/Taipei"
    idx = pd.date_range("2024-01-02 09:00", periods=5, freq="5min", tz=tz)
    assert bt._infer_freq(idx) == "5min"


def test_infer_freq_1min() -> None:
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    tz = "Asia/Taipei"
    idx = pd.date_range("2024-01-02 09:00", periods=5, freq="1min", tz=tz)
    assert bt._infer_freq(idx) == "1min"


def test_infer_freq_60min() -> None:
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    tz = "Asia/Taipei"
    idx = pd.date_range("2024-01-02 09:00", periods=5, freq="60min", tz=tz)
    assert bt._infer_freq(idx) == "60min"


def test_infer_freq_empty_returns_1day() -> None:
    bt = EventDrivenBacktester.__new__(EventDrivenBacktester)
    assert bt._infer_freq(pd.DatetimeIndex([])) == "1day"


def test_strategy_no_modification_needed() -> None:
    df = _build_ma_cross_event_fixture()
    strategy = MACrossStrategy(ma_short=2, ma_long=3)
    calc = CostCalculator(slippage_ticks=0)

    vec_result = VectorizedBacktester(initial_capital=1_000_000, cost_calculator=calc).run(strategy, df)
    event_backtester = EventDrivenBacktester(initial_capital=1_000_000, cost_calculator=calc)
    first_event_result = event_backtester.run(strategy, df)
    second_event_result = event_backtester.run(strategy, df)

    assert vec_result.total_trades > 0
    assert first_event_result.total_trades > 0
    assert first_event_result.total_trades == second_event_result.total_trades
    assert first_event_result.trades["entry_date"].tolist() == second_event_result.trades["entry_date"].tolist()
    assert first_event_result.trades["exit_date"].tolist() == second_event_result.trades["exit_date"].tolist()
    assert first_event_result.total_return == pytest.approx(second_event_result.total_return, abs=1e-9)
