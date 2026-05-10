"""Event-driven backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.backtest._helpers import (
    build_cost_calculator_from_config,
    calculate_max_buy_quantity,
    is_etf_symbol,
)
from src.backtest.account import SimpleAccount
from src.backtest.base import BacktesterBase
from src.backtest.cost import CostCalculator
from src.backtest.events import BarEvent, FillEvent, OrderEvent
from src.backtest.metrics import BacktestResult, calculate_metrics
from src.strategy.base import StrategyBase


@dataclass
class _OpenPosition:
    entry_date: datetime
    quantity: int
    entry_notional_total: float
    buy_fee_total: float


class EventDrivenBacktester(BacktesterBase):
    """
    Event-driven backtest engine.

    Signal generated on bar t is executed on bar t+1 open.
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        cost_calculator: CostCalculator | None = None,
    ) -> None:
        self.initial_capital = float(initial_capital)
        self.cost_calculator = cost_calculator or build_cost_calculator_from_config()

    def run(self, strategy: StrategyBase, data: pd.DataFrame) -> BacktestResult:
        df = self._prepare_data(data)
        if df.empty:
            return calculate_metrics(pd.Series(dtype="float64"), pd.DataFrame())

        strategy.reset_runtime_state()
        account = SimpleAccount(self.initial_capital)
        pending_orders: list[OrderEvent] = []
        equity_records: list[dict[str, Any]] = []
        trade_records: list[dict[str, Any]] = []
        open_positions: dict[str, _OpenPosition] = {}
        latest_prices: dict[str, float] = {}

        bars = list(df.itertuples())
        freq = self._infer_freq(df.index)

        for bar in bars:
            bar_event = self._to_bar_event(bar, freq=freq)

            # Step 1: execute pending orders whose symbol matches the current bar open.
            # Orders for other symbols are deferred until their matching bar arrives.
            if pending_orders:
                deferred: list[OrderEvent] = []
                for order in pending_orders:
                    if order.symbol != bar_event.symbol:
                        deferred.append(order)
                        continue
                    fill = self._simulate_fill(order=order, bar=bar_event, account=account)
                    if fill is None:
                        continue
                    account.apply_fill(fill)
                    strategy.on_fill(fill, account)
                    round_trip = self._update_round_trip_records(fill=fill, open_positions=open_positions)
                    if round_trip is not None:
                        trade_records.append(round_trip)
                pending_orders = deferred

            # Step 2: strategy generates orders on current bar.
            new_orders = strategy.on_bar(bar_event, account) or []
            pending_orders.extend(new_orders)

            # Step 3: mark-to-market using latest known price for every held symbol.
            latest_prices[bar_event.symbol] = bar_event.close
            equity_records.append(
                {
                    "date": bar_event.timestamp,
                    "equity": account.get_total_value(latest_prices),
                }
            )

        # Pending orders generated on the final bar are intentionally discarded.
        return self._build_result(equity_records=equity_records, trade_records=trade_records)

    @staticmethod
    def _update_round_trip_records(
        fill: FillEvent,
        open_positions: dict[str, _OpenPosition],
    ) -> dict[str, Any] | None:
        symbol = fill.symbol
        quantity = int(fill.quantity)
        notional = float(fill.fill_price) * quantity
        fees = float(fill.commission + fill.tax)

        if fill.side == "BUY":
            position = open_positions.get(symbol)
            if position is None:
                open_positions[symbol] = _OpenPosition(
                    entry_date=fill.timestamp,
                    quantity=quantity,
                    entry_notional_total=notional,
                    buy_fee_total=fees,
                )
            else:
                position.quantity += quantity
                position.entry_notional_total += notional
                position.buy_fee_total += fees
            return None

        if fill.side != "SELL":
            return None

        position = open_positions.get(symbol)
        if position is None or position.quantity <= 0:
            return None

        qty_before = position.quantity
        if quantity > qty_before:
            return None
        avg_entry_price = position.entry_notional_total / qty_before
        avg_buy_fee_per_share = position.buy_fee_total / qty_before

        allocated_entry_notional = avg_entry_price * quantity
        allocated_buy_fees = avg_buy_fee_per_share * quantity
        sell_proceeds_net = notional - fees
        pnl = sell_proceeds_net - allocated_entry_notional - allocated_buy_fees

        position.quantity -= quantity
        position.entry_notional_total -= allocated_entry_notional
        position.buy_fee_total -= allocated_buy_fees
        if position.quantity == 0:
            open_positions.pop(symbol, None)

        return {
            "entry_date": position.entry_date,
            "exit_date": fill.timestamp,
            "side": "LONG",
            "quantity": quantity,
            "entry_price": float(avg_entry_price),
            "exit_price": float(fill.fill_price),
            "pnl": float(pnl),
        }

    @staticmethod
    def _prepare_data(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy(deep=True)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).set_index("date")
        else:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df[~df.index.isna()]

        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                raise ValueError(f"Input data must include '{col}' column.")
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if "volume" not in df.columns:
            df["volume"] = 0
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

        if "symbol" not in df.columns:
            df["symbol"] = "UNKNOWN"
        df["symbol"] = df["symbol"].fillna("UNKNOWN").astype(str)

        return df.dropna(subset=["open", "high", "low", "close"]).sort_index()

    @staticmethod
    def _to_bar_event(bar: Any, freq: str) -> BarEvent:
        timestamp = pd.Timestamp(bar.Index)
        if timestamp.tz is None:
            timestamp = timestamp.tz_localize("UTC")

        symbol = str(getattr(bar, "symbol", "UNKNOWN") or "UNKNOWN")
        return BarEvent(
            symbol=symbol,
            timestamp=timestamp.to_pydatetime(),
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=int(getattr(bar, "volume", 0)),
            freq=freq,
        )

    def _simulate_fill(
        self,
        order: OrderEvent,
        bar: BarEvent,
        account: SimpleAccount,
    ) -> FillEvent | None:
        side = order.side.upper()
        if order.order_type == "MARKET":
            fill_price = self.cost_calculator.apply_slippage(price=bar.open, side=side)
        elif order.order_type == "LIMIT":
            if order.price is None:
                return None
            if bar.low <= float(order.price) <= bar.high:
                fill_price = float(order.price)
            else:
                return None
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        is_etf = is_etf_symbol(order.symbol)
        quantity = int(order.quantity)
        if side == "BUY":
            quantity = self._resolve_buy_quantity(
                requested_qty=quantity,
                cash=account.get_cash(),
                fill_price=float(fill_price),
                is_etf=is_etf,
            )
            if quantity <= 0:
                return None

        cost = self.cost_calculator.calculate(
            price=fill_price,
            quantity=quantity,
            side=side,
            is_etf=is_etf,
        )

        return FillEvent(
            symbol=order.symbol,
            side=side,
            quantity=quantity,
            fill_price=float(fill_price),
            commission=float(cost.commission),
            tax=float(cost.tax),
            timestamp=bar.timestamp,
        )

    def _resolve_buy_quantity(
        self,
        *,
        requested_qty: int,
        cash: float,
        fill_price: float,
        is_etf: bool,
    ) -> int:
        if requested_qty <= 0 or cash <= 0 or fill_price <= 0:
            return 0
        max_qty = calculate_max_buy_quantity(
            cash=cash,
            price=fill_price,
            cost_calculator=self.cost_calculator,
            is_etf=is_etf,
        )
        return min(int(requested_qty), max_qty)

    @staticmethod
    def _build_result(equity_records: list[dict[str, Any]], trade_records: list[dict[str, Any]]) -> BacktestResult:
        if not equity_records:
            return calculate_metrics(pd.Series(dtype="float64"), pd.DataFrame())

        equity_curve = pd.Series(
            [record["equity"] for record in equity_records],
            index=pd.to_datetime([record["date"] for record in equity_records]),
            dtype="float64",
        )
        trades_df = pd.DataFrame(trade_records)
        return calculate_metrics(equity_curve=equity_curve, trades=trades_df)

    @staticmethod
    def _infer_freq(index: pd.Index) -> str:
        if len(index) < 3:
            return "1day"
        inferred = pd.infer_freq(pd.DatetimeIndex(index))
        if not inferred:
            return "1day"

        alias = inferred.upper()
        if alias in {"D", "B"}:
            return "1day"
        # Old pandas: "T", "5T" …  New pandas 2.2+: "min", "5min" …
        if alias.endswith("T"):
            value = alias[:-1] or "1"
            return f"{value}min"
        if alias.endswith("MIN"):
            value = alias[:-3] or "1"
            return f"{value}min"
        # Old pandas: "H", "2H" …  New pandas 2.2+: "h", "2h" …
        if alias.endswith("H"):
            return "60min"
        return "1day"
