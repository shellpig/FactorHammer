from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.backtest.account import SimpleAccount
from src.backtest.events import FillEvent


def _fill(
    *,
    side: str,
    quantity: int,
    fill_price: float,
    commission: float,
    tax: float = 0.0,
    symbol: str = "2330",
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        side=side,
        quantity=quantity,
        fill_price=fill_price,
        commission=commission,
        tax=tax,
        timestamp=datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc),
    )


def test_initial_state() -> None:
    account = SimpleAccount(initial_capital=1_000_000)

    assert account.get_cash() == pytest.approx(1_000_000.0, abs=1e-9)
    assert account.get_positions() == {}
    assert account.get_position("2330") == 0
    assert account.get_cost_basis("2330") == pytest.approx(0.0, abs=1e-9)


def test_buy_reduces_cash() -> None:
    account = SimpleAccount(initial_capital=1_000_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=85.0))

    assert account.get_cash() == pytest.approx(899_915.0, abs=1e-9)
    assert account.get_position("2330") == 1000


def test_sell_increases_cash() -> None:
    account = SimpleAccount(initial_capital=1_000_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=85.0))
    account.apply_fill(_fill(side="SELL", quantity=1000, fill_price=110.0, commission=94.0, tax=330.0))

    assert account.get_cash() == pytest.approx(1_009_491.0, abs=1e-9)
    assert account.get_position("2330") == 0


def test_buy_then_sell_position_zero() -> None:
    account = SimpleAccount(initial_capital=1_000_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=85.0))
    account.apply_fill(_fill(side="SELL", quantity=1000, fill_price=110.0, commission=94.0, tax=330.0))

    assert "2330" not in account.get_positions()
    assert account.get_cost_basis("2330") == pytest.approx(0.0, abs=1e-9)


def test_oversell_raises() -> None:
    account = SimpleAccount(initial_capital=1_000_000)

    with pytest.raises(ValueError):
        account.apply_fill(_fill(side="SELL", quantity=1000, fill_price=110.0, commission=94.0, tax=330.0))


def test_cost_basis_weighted_average() -> None:
    account = SimpleAccount(initial_capital=1_000_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=85.0))
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=120.0, commission=102.0))

    assert account.get_position("2330") == 2000
    assert account.get_cost_basis("2330") == pytest.approx(110.0, abs=1e-9)


def test_total_value() -> None:
    account = SimpleAccount(initial_capital=500_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=0.0))

    assert account.get_cash() == pytest.approx(400_000.0, abs=1e-9)
    assert account.get_total_value({"2330": 220.0}) == pytest.approx(620_000.0, abs=1e-9)


def test_unrealized_pnl() -> None:
    account = SimpleAccount(initial_capital=1_000_000)
    account.apply_fill(_fill(side="BUY", quantity=1000, fill_price=100.0, commission=85.0))

    assert account.get_unrealized_pnl("2330", current_price=120.0) == pytest.approx(20_000.0, abs=1e-9)
