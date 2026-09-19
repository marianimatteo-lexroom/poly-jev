from __future__ import annotations

import pytest
from factories import make_market

from reflex import risk_manager
from reflex.config import Settings
from reflex.edge_engine import TradeSignal


class FakeLedger:
    def __init__(self, open_positions: int = 0, exposure: float = 0.0):
        self._open_positions = open_positions
        self._exposure = exposure

    def open_position_count(self) -> int:
        return self._open_positions

    def open_exposure_usd(self, condition_id: str | None = None) -> float:
        return self._exposure


def make_signal(yes_price=0.2, fair_probability=0.9, side="YES") -> TradeSignal:
    market = make_market(yes_price=yes_price)
    edge = (fair_probability - yes_price) if side == "YES" else ((1 - fair_probability) - (1 - yes_price))
    return TradeSignal(
        market=market, side=side, fair_probability=fair_probability, market_price=yes_price, edge=edge, confidence=0.9
    )


def test_kelly_fraction_yes_side():
    f = risk_manager.kelly_fraction(fair_probability=0.6, price=0.4, side="YES")
    assert f == pytest.approx((0.6 - 0.4) / (1 - 0.4))


def test_kelly_fraction_no_side():
    f = risk_manager.kelly_fraction(fair_probability=0.4, price=0.6, side="NO")
    assert f == pytest.approx(((1 - 0.4) - (1 - 0.6)) / (1 - (1 - 0.6)))


def test_kelly_fraction_negative_edge_clamped_to_zero():
    assert risk_manager.kelly_fraction(0.5, 0.9, "YES") == 0.0


def test_size_trade_respects_max_position_cap():
    signal = make_signal()
    settings = Settings(
        bankroll_usd=10_000,
        kelly_fraction=1.0,
        max_position_usd=25.0,
        max_position_fraction=0.5,
        max_market_exposure_usd=1000.0,
        min_liquidity_usd=0,
        min_volume_usd=0,
        max_open_positions=10,
        max_daily_loss_usd=1000,
    )
    ledger = FakeLedger()

    size = risk_manager.size_trade(settings, ledger, signal, daily_realized_loss=0.0)

    assert size == 25.0


def test_size_trade_blocked_when_daily_loss_limit_hit():
    signal = make_signal()
    settings = Settings(max_daily_loss_usd=50.0)
    ledger = FakeLedger()

    size = risk_manager.size_trade(settings, ledger, signal, daily_realized_loss=60.0)

    assert size == 0.0


def test_size_trade_blocked_when_too_many_open_positions():
    signal = make_signal()
    settings = Settings(max_open_positions=1)
    ledger = FakeLedger(open_positions=1)

    size = risk_manager.size_trade(settings, ledger, signal, daily_realized_loss=0.0)

    assert size == 0.0


def test_size_trade_blocked_when_market_exposure_cap_hit():
    signal = make_signal()
    settings = Settings(max_market_exposure_usd=50.0)
    ledger = FakeLedger(exposure=50.0)

    size = risk_manager.size_trade(settings, ledger, signal, daily_realized_loss=0.0)

    assert size == 0.0


def test_size_trade_blocked_when_liquidity_too_low():
    signal = make_signal()
    settings = Settings(min_liquidity_usd=1_000_000)
    ledger = FakeLedger()

    size = risk_manager.size_trade(settings, ledger, signal, daily_realized_loss=0.0)

    assert size == 0.0
