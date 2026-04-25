from __future__ import annotations

import pytest

from src.backtest.cost import CostCalculator


def test_tick_size_boundaries() -> None:
    calc = CostCalculator()

    assert calc.get_tick_size(9.99) == 0.01
    assert calc.get_tick_size(10.00) == 0.05
    assert calc.get_tick_size(49.99) == 0.05
    assert calc.get_tick_size(50.00) == 0.10
    assert calc.get_tick_size(99.99) == 0.10
    assert calc.get_tick_size(100.00) == 0.50
    assert calc.get_tick_size(499.99) == 0.50
    assert calc.get_tick_size(500.00) == 1.00
    assert calc.get_tick_size(999.99) == 1.00
    assert calc.get_tick_size(1000.00) == 5.00


def test_buy_no_tax() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=1000, quantity=100, side="BUY")

    assert cost.tax == 0.0


def test_sell_has_tax() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=1000, quantity=100, side="SELL")

    assert cost.tax == 300.0


def test_etf_tax_rate() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=1000, quantity=100, side="SELL", is_etf=True)

    assert cost.tax == 100.0


def test_commission_discount() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=1000, quantity=100, side="BUY")

    assert cost.commission == pytest.approx(85.5, abs=0.01)


def test_commission_minimum_20() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=1, quantity=10, side="BUY")

    assert cost.commission == 20.0


def test_slippage_buy() -> None:
    calc = CostCalculator()
    slipped_price = calc.apply_slippage(price=100, side="BUY")

    assert slipped_price == pytest.approx(100.5, abs=0.01)


def test_known_trade_total() -> None:
    calc = CostCalculator()
    cost = calc.calculate(price=500, quantity=1000, side="BUY")

    assert cost.commission == pytest.approx(427.5, abs=0.01)
    assert cost.tax == 0.0
    assert cost.slippage == pytest.approx(1000.0, abs=0.01)
    assert cost.total == pytest.approx(1427.5, abs=0.01)
