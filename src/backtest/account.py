"""Account state models for event-driven backtesting."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.backtest.events import FillEvent


class Account(ABC):
    """Abstract account interface."""

    @abstractmethod
    def get_cash(self) -> float:
        """Return current cash balance."""

    @abstractmethod
    def get_position(self, symbol: str) -> int:
        """Return current position quantity for one symbol."""

    @abstractmethod
    def get_positions(self) -> dict[str, int]:
        """Return all positions."""

    @abstractmethod
    def apply_fill(self, fill: FillEvent) -> None:
        """Apply one fill and update account state."""

    @abstractmethod
    def get_total_value(self, current_prices: dict[str, float]) -> float:
        """Return account total equity value."""

    @abstractmethod
    def get_cost_basis(self, symbol: str) -> float:
        """Return average cost basis for one symbol."""


class SimpleAccount(Account):
    """Single-account implementation used in v1."""

    def __init__(self, initial_capital: float):
        self._initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions: dict[str, int] = {}
        self.cost_basis: dict[str, float] = {}
        self._history: list[dict] = []

    def get_cash(self) -> float:
        return float(self.cash)

    def get_position(self, symbol: str) -> int:
        return int(self.positions.get(symbol, 0))

    def get_positions(self) -> dict[str, int]:
        return dict(self.positions)

    def get_cost_basis(self, symbol: str) -> float:
        return float(self.cost_basis.get(symbol, 0.0))

    def apply_fill(self, fill: FillEvent) -> None:
        symbol = fill.symbol
        side = fill.side
        quantity = int(fill.quantity)
        fill_price = float(fill.fill_price)
        commission = float(fill.commission)
        tax = float(fill.tax)

        if side == "BUY":
            previous_qty = self.positions.get(symbol, 0)
            previous_cost = self.cost_basis.get(symbol, 0.0)
            new_qty = previous_qty + quantity
            new_cost_basis = ((previous_cost * previous_qty) + (fill_price * quantity)) / new_qty

            self.cash -= (fill_price * quantity) + commission
            self.positions[symbol] = new_qty
            self.cost_basis[symbol] = float(new_cost_basis)
        elif side == "SELL":
            previous_qty = self.positions.get(symbol, 0)
            if quantity > previous_qty:
                raise ValueError(f"Oversell detected for {symbol}: have {previous_qty}, sell {quantity}.")

            self.cash += (fill_price * quantity) - commission - tax
            new_qty = previous_qty - quantity
            if new_qty == 0:
                self.positions.pop(symbol, None)
                self.cost_basis.pop(symbol, None)
            else:
                self.positions[symbol] = new_qty
        else:
            raise ValueError(f"Invalid fill side: {side}")

        self._history.append(
            {
                "timestamp": fill.timestamp,
                "action": fill.side,
                "symbol": symbol,
                "quantity": quantity,
                "price": fill_price,
                "cash_after": float(self.cash),
                "positions_after": dict(self.positions),
            }
        )

    def get_total_value(self, current_prices: dict[str, float]) -> float:
        total = float(self.cash)
        for symbol, quantity in self.positions.items():
            if symbol not in current_prices:
                raise KeyError(f"Missing current price for symbol: {symbol}")
            total += int(quantity) * float(current_prices[symbol])
        return float(total)

    def get_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        quantity = self.get_position(symbol)
        if quantity == 0:
            return 0.0
        return float(quantity * (float(current_price) - self.get_cost_basis(symbol)))

    def get_history(self) -> list[dict]:
        return list(self._history)
