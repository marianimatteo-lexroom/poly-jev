from __future__ import annotations

from .ledger import Ledger
from .polymarket_client import ClobMarketData, GammaClient


def realized_pnl_since(ledger: Ledger, gamma: GammaClient, since_ts: float) -> float:
    """Sums realized PnL for fills recorded since `since_ts` whose markets
    have since resolved. Unresolved positions contribute 0 here — see
    `unrealized_pnl_since` for those.
    """
    pnl = 0.0
    for fill in ledger.read_all():
        if fill.timestamp < since_ts:
            continue

        outcome = gamma.fetch_resolution(fill.condition_id)
        if outcome is None:
            continue

        won = outcome == fill.side
        shares = fill.size_usd / fill.price if fill.price else 0.0
        pnl += (shares - fill.size_usd) if won else -fill.size_usd

    return pnl


def unrealized_pnl_since(ledger: Ledger, gamma: GammaClient, clob: ClobMarketData, since_ts: float) -> float:
    """Marks still-open positions to the current live sell price, so the
    daily-loss kill switch can see intraday drawdown on positions that
    haven't resolved yet — not just realized losses on closed markets.

    Each fill/market pair is only priced once per call; a large open book
    means one Gamma + one CLOB call per open condition_id.
    """
    fills = [f for f in ledger.read_all() if f.timestamp >= since_ts]
    pnl = 0.0
    priced: set[tuple[str, str]] = set()

    for fill in fills:
        key = (fill.condition_id, fill.side)
        if key in priced:
            continue
        priced.add(key)

        if gamma.fetch_resolution(fill.condition_id) is not None:
            continue  # already resolved — counted in realized_pnl_since instead

        current_price = clob.get_best_bid(fill.token_id)
        if current_price is None:
            continue

        shares = fill.size_usd / fill.price if fill.price else 0.0
        market_value = shares * current_price
        pnl += market_value - fill.size_usd

    return pnl
