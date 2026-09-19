from __future__ import annotations

from .config import Settings
from .edge_engine import TradeSignal
from .ledger import Ledger


def kelly_fraction(fair_probability: float, price: float, side: str) -> float:
    """Kelly fraction for a binary contract paying $1 on the traded side.

    Buying `side` at `price` with true probability `p` of that side winning:
    f* = (p - price) / (1 - price). Clamped to 0 when there's no edge.
    """
    if side == "YES":
        p, c = fair_probability, price
    else:
        p, c = 1 - fair_probability, 1 - price

    if c <= 0 or c >= 1:
        return 0.0
    return max(0.0, (p - c) / (1 - c))


def size_trade(settings: Settings, ledger: Ledger, signal: TradeSignal, daily_realized_loss: float) -> float:
    """Returns a USD size to trade, or 0.0 if the trade should be skipped.

    Every cap here is a hard pre-trade gate — sizing never exceeds them,
    regardless of how large the Kelly-implied size is.
    """
    if ledger.open_position_count() >= settings.max_open_positions:
        return 0.0

    existing_exposure = ledger.open_exposure_usd(signal.market.condition_id)
    if existing_exposure >= settings.max_market_exposure_usd:
        return 0.0

    if signal.market.liquidity_usd < settings.min_liquidity_usd:
        return 0.0
    if signal.market.volume_usd < settings.min_volume_usd:
        return 0.0
    if daily_realized_loss >= settings.max_daily_loss_usd:
        return 0.0

    f_kelly = kelly_fraction(signal.fair_probability, signal.market_price, signal.side)
    f_kelly *= settings.kelly_fraction  # fractional Kelly for variance control

    size = f_kelly * settings.bankroll_usd
    size = min(size, settings.max_position_usd, settings.bankroll_usd * settings.max_position_fraction)
    size = min(size, settings.max_market_exposure_usd - existing_exposure)

    return max(0.0, round(size, 2))
