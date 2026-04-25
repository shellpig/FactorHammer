"""Backtest package."""

from src.backtest.cost import CostCalculator, TradeCost
from src.backtest.base import BacktesterBase
from src.backtest.account import Account, SimpleAccount
from src.backtest.engine_vec import VectorizedBacktester
from src.backtest.events import BarEvent, FillEvent, OrderEvent
from src.backtest.metrics import BacktestResult, calculate_max_drawdown, calculate_metrics, calculate_monthly_returns
from src.backtest.report import TearsheetReport

__all__ = [
    "CostCalculator",
    "TradeCost",
    "BacktesterBase",
    "Account",
    "SimpleAccount",
    "VectorizedBacktester",
    "BarEvent",
    "OrderEvent",
    "FillEvent",
    "BacktestResult",
    "calculate_metrics",
    "calculate_max_drawdown",
    "calculate_monthly_returns",
    "TearsheetReport",
]
