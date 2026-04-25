"""Abstract interfaces for backtest engines."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.backtest.metrics import BacktestResult
from src.strategy.base import StrategyBase


class BacktesterBase(ABC):
    """Base protocol of all backtest engines."""

    @abstractmethod
    def run(self, strategy: StrategyBase, data: pd.DataFrame) -> BacktestResult:
        """Run backtest and return result."""
