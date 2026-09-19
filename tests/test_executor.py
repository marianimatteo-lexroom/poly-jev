from __future__ import annotations

import pytest

from reflex.config import Settings
from reflex.executor import Executor, ExecutorError, OrderRequest
from reflex.ledger import Ledger


def make_order(**overrides) -> OrderRequest:
    base = dict(
        condition_id="0xabc",
        question="Will it happen?",
        side="YES",
        token_id="yes-token",
        price=0.5,
        size_usd=10.0,
        tick_size=0.01,
        min_order_size=5.0,
        neg_risk=False,
    )
    base.update(overrides)
    return OrderRequest(**base)


def test_execute_rejects_order_below_min_size(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    executor = Executor(Settings(dry_run=True), ledger)
    # min_order_size=5 shares @ price=0.5 => $2.50 minimum; $1 is too small.
    order = make_order(price=0.5, size_usd=1.0, min_order_size=5.0)

    with pytest.raises(ExecutorError):
        executor.execute(order)


def test_execute_paper_trades_by_default(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    executor = Executor(Settings(dry_run=True), ledger)
    order = make_order(price=0.5, size_usd=10.0, min_order_size=5.0)

    fill = executor.execute(order)

    assert fill.mode == "paper"
    assert fill.token_id == "yes-token"
    assert ledger.open_exposure_usd("0xabc") == 10.0
