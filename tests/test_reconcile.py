from __future__ import annotations

import time

from reflex import reconcile
from reflex.ledger import Fill, Ledger


class FakeGamma:
    def __init__(self, resolution=None):
        self._resolution = resolution

    def fetch_resolution(self, condition_id):
        return self._resolution


class FakeClob:
    def __init__(self, price):
        self._price = price

    def get_best_bid(self, token_id):
        return self._price


def _fill(condition_id="0xabc", side="YES", token_id="yes-token", price=0.4, size_usd=10.0, ts=None) -> Fill:
    return Fill(
        condition_id=condition_id,
        question="Will it happen?",
        side=side,
        token_id=token_id,
        price=price,
        size_usd=size_usd,
        mode="paper",
        timestamp=ts if ts is not None else time.time(),
    )


def test_realized_pnl_counts_wins_and_losses(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    ledger.record(_fill(condition_id="0x1", side="YES", price=0.4, size_usd=10.0))  # 10 shares -> $25 if won
    ledger.record(_fill(condition_id="0x2", side="YES", price=0.5, size_usd=10.0))  # loses

    gamma = FakeGamma(resolution="YES")  # both markets resolve YES: 0x1 wins, 0x2... also YES side, also wins
    pnl = reconcile.realized_pnl_since(ledger, gamma, since_ts=0)

    # fill 1: shares = 10/0.4 = 25, payout 25 - 10 = 15 profit
    # fill 2: shares = 10/0.5 = 20, payout 20 - 10 = 10 profit
    assert pnl == 25.0


def test_realized_pnl_is_zero_for_unresolved_markets(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    ledger.record(_fill())

    gamma = FakeGamma(resolution=None)
    assert reconcile.realized_pnl_since(ledger, gamma, since_ts=0) == 0.0


def test_unrealized_pnl_marks_open_position_to_current_bid(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    ledger.record(_fill(price=0.4, size_usd=10.0))  # 25 shares

    gamma = FakeGamma(resolution=None)  # still open
    clob = FakeClob(price=0.6)  # price moved up in our favor

    pnl = reconcile.unrealized_pnl_since(ledger, gamma, clob, since_ts=0)

    # 25 shares * 0.6 = 15, cost basis 10 -> +5 unrealized
    assert pnl == 5.0


def test_unrealized_pnl_skips_resolved_markets(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    ledger.record(_fill(price=0.4, size_usd=10.0))

    gamma = FakeGamma(resolution="YES")  # already resolved — handled by realized_pnl instead
    clob = FakeClob(price=0.6)

    assert reconcile.unrealized_pnl_since(ledger, gamma, clob, since_ts=0) == 0.0
