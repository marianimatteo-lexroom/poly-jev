from __future__ import annotations

from .ledger import Ledger
from .polymarket_client import GammaClient


def realized_pnl_since(ledger: Ledger, gamma: GammaClient, since_ts: float) -> float:
    """Sums realized PnL for fills recorded since `since_ts` whose markets
    have since resolved. Unresolved positions contribute 0 until they settle,
    so this understates risk for a portfolio full of still-open longshots —
    it's meant as a daily-loss kill switch, not full mark-to-market PnL.
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
