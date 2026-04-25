"""Market friction cost calculator for Taiwan stocks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeCost:
    """Single-trade cost breakdown."""

    commission: float
    tax: float
    slippage: float
    total: float


class CostCalculator:
    """Calculate commission, tax, and slippage for one trade."""

    def __init__(
        self,
        commission_rate: float = 0.001425,
        commission_discount: float = 0.6,
        tax_rate: float = 0.003,
        etf_tax_rate: float = 0.001,
        slippage_ticks: int = 1,
    ) -> None:
        self.effective_commission_rate = float(commission_rate) * float(commission_discount)
        self.tax_rate = float(tax_rate)
        self.etf_tax_rate = float(etf_tax_rate)
        self.slippage_ticks = int(slippage_ticks)

    def calculate(
        self,
        price: float,
        quantity: int,
        side: str,
        is_etf: bool = False,
    ) -> TradeCost:
        side_normalized = side.upper()
        if side_normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be 'BUY' or 'SELL'.")
        if price <= 0:
            raise ValueError("price must be positive.")
        if quantity <= 0:
            raise ValueError("quantity must be positive.")

        turnover = float(price) * int(quantity)
        commission = max(turnover * self.effective_commission_rate, 20.0)

        if side_normalized == "SELL":
            tax_rate = self.etf_tax_rate if is_etf else self.tax_rate
            tax = turnover * tax_rate
        else:
            tax = 0.0

        slippage = self.get_tick_size(price) * self.slippage_ticks * int(quantity)
        total = commission + tax + slippage

        return TradeCost(
            commission=float(commission),
            tax=float(tax),
            slippage=float(slippage),
            total=float(total),
        )

    @staticmethod
    def get_tick_size(price: float) -> float:
        """Return Taiwan stock tick size based on current price."""
        if price < 10:
            return 0.01
        if price < 50:
            return 0.05
        if price < 100:
            return 0.10
        if price < 500:
            return 0.50
        if price < 1000:
            return 1.00
        return 5.00

    def apply_slippage(self, price: float, side: str) -> float:
        """Return simulated execution price after slippage."""
        side_normalized = side.upper()
        if side_normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be 'BUY' or 'SELL'.")
        tick_size = self.get_tick_size(price)
        adjust = tick_size * self.slippage_ticks
        if side_normalized == "BUY":
            return float(price + adjust)
        return float(price - adjust)
