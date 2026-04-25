"""Vectorized backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.base import BacktesterBase
from src.backtest.cost import CostCalculator
from src.backtest.metrics import BacktestResult, calculate_metrics
from src.core.config import get_config
from src.strategy.base import StrategyBase


ETF_SYMBOLS = {
    "0050",
    "0051",
    "0056",
    "006208",
    "00878",
    "00919",
}


@dataclass
class _OpenTrade:
    entry_date: pd.Timestamp
    entry_price: float
    quantity: int
    buy_cost_total: float


class VectorizedBacktester(BacktesterBase):
    """
    Vectorized backtest engine with next-bar execution semantics.

    Signal generated on bar t is executed on bar t+1 open.
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        cost_calculator: CostCalculator | None = None,
    ) -> None:
        self.initial_capital = float(initial_capital)
        self.cost_calculator = cost_calculator or self._build_cost_calculator_from_config()

    def run(self, strategy: StrategyBase, data: pd.DataFrame) -> BacktestResult:
        df = self._prepare_data(data)
        if df.empty:
            return calculate_metrics(pd.Series(dtype="float64"), pd.DataFrame())

        raw_signals = strategy.generate_signals(df)
        signals = pd.Series(raw_signals, index=df.index).fillna(0).astype("int8")
        signals = self._drop_warmup_signals(strategy, signals)

        symbol = self._infer_symbol(df)
        is_etf = self._is_etf_symbol(symbol)

        cash = self.initial_capital
        quantity = 0
        pending_action: str | None = None
        open_trade: _OpenTrade | None = None
        trade_records: list[dict] = []
        equity_records: list[dict] = []

        for i, (dt, row) in enumerate(df.iterrows()):
            open_price = float(row["open"])
            close_price = float(row["close"])

            if pending_action == "BUY" and quantity == 0:
                buy_qty = self._calculate_order_quantity(cash, open_price)
                if buy_qty > 0:
                    buy_cost = self.cost_calculator.calculate(
                        price=open_price,
                        quantity=buy_qty,
                        side="BUY",
                        is_etf=is_etf,
                    )
                    cash -= (open_price * buy_qty) + buy_cost.total
                    quantity = buy_qty
                    open_trade = _OpenTrade(
                        entry_date=dt,
                        entry_price=open_price,
                        quantity=buy_qty,
                        buy_cost_total=buy_cost.total,
                    )

            elif pending_action == "SELL" and quantity > 0 and open_trade is not None:
                sell_cost = self.cost_calculator.calculate(
                    price=open_price,
                    quantity=quantity,
                    side="SELL",
                    is_etf=is_etf,
                )
                cash += (open_price * quantity) - sell_cost.total

                pnl = ((open_price - open_trade.entry_price) * quantity) - open_trade.buy_cost_total - sell_cost.total
                trade_records.append(
                    {
                        "entry_date": open_trade.entry_date,
                        "exit_date": dt,
                        "side": "LONG",
                        "quantity": quantity,
                        "entry_price": open_trade.entry_price,
                        "exit_price": open_price,
                        "pnl": float(pnl),
                    }
                )
                quantity = 0
                open_trade = None

            pending_action = None
            signal = int(signals.iloc[i])
            if signal == 1 and quantity == 0:
                pending_action = "BUY"
            elif signal == -1 and quantity > 0:
                pending_action = "SELL"

            equity = cash + (quantity * close_price)
            equity_records.append({"date": dt, "equity": float(equity)})

        if quantity > 0 and open_trade is not None:
            final_dt = pd.Timestamp(df.index[-1])
            final_close = float(df.iloc[-1]["close"])
            final_sell_cost = self.cost_calculator.calculate(
                price=final_close,
                quantity=quantity,
                side="SELL",
                is_etf=is_etf,
            )
            cash += (final_close * quantity) - final_sell_cost.total
            pnl = ((final_close - open_trade.entry_price) * quantity) - open_trade.buy_cost_total - final_sell_cost.total
            trade_records.append(
                {
                    "entry_date": open_trade.entry_date,
                    "exit_date": final_dt,
                    "side": "LONG",
                    "quantity": quantity,
                    "entry_price": open_trade.entry_price,
                    "exit_price": final_close,
                    "pnl": float(pnl),
                }
            )
            quantity = 0
            open_trade = None
            equity_records[-1]["equity"] = float(cash)

        equity_curve = pd.Series(
            [record["equity"] for record in equity_records],
            index=pd.to_datetime([record["date"] for record in equity_records]),
            dtype="float64",
        )
        trades_df = pd.DataFrame(trade_records)
        return calculate_metrics(equity_curve=equity_curve, trades=trades_df)

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

        df = df.dropna(subset=["open", "high", "low", "close"]).sort_index()
        return df

    @staticmethod
    def _drop_warmup_signals(strategy: StrategyBase, signals: pd.Series) -> pd.Series:
        ma_short = int(getattr(strategy, "ma_short", 0) or 0)
        ma_long = int(getattr(strategy, "ma_long", 0) or 0)
        warmup = max(ma_short, ma_long)
        out = signals.copy()
        if warmup > 0:
            out.iloc[:warmup] = 0
        return out

    @staticmethod
    def _calculate_order_quantity(cash: float, price: float) -> int:
        whole_lot_qty = int((cash // price) // 1000) * 1000
        if whole_lot_qty > 0:
            return whole_lot_qty
        odd_lot_qty = int(cash // price)
        return max(odd_lot_qty, 0)

    @staticmethod
    def _infer_symbol(df: pd.DataFrame) -> str:
        if "symbol" not in df.columns or df["symbol"].dropna().empty:
            return "UNKNOWN"
        return str(df["symbol"].dropna().iloc[0])

    @staticmethod
    def _is_etf_symbol(symbol: str) -> bool:
        if symbol in ETF_SYMBOLS:
            return True
        return len(symbol) == 4 and symbol.startswith("00")

    @staticmethod
    def _build_cost_calculator_from_config() -> CostCalculator:
        try:
            cfg = get_config().get("backtest", {})
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}

        return CostCalculator(
            commission_rate=float(cfg.get("commission_rate", 0.001425)),
            commission_discount=float(cfg.get("commission_discount", 0.6)),
            tax_rate=float(cfg.get("tax_rate", 0.003)),
            etf_tax_rate=float(cfg.get("etf_tax_rate", 0.001)),
            slippage_ticks=int(cfg.get("slippage_ticks", 1)),
        )
