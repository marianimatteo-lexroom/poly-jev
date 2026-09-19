from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings
from .ledger import Fill, Ledger


@dataclass(frozen=True)
class OrderRequest:
    condition_id: str
    question: str
    side: Literal["YES", "NO"]
    token_id: str
    price: float
    size_usd: float


class Executor:
    """Places (or simulates) orders. Defaults to paper trading — a live
    order is only ever sent when `settings.dry_run` is explicitly False."""

    def __init__(self, settings: Settings, ledger: Ledger):
        self._settings = settings
        self._ledger = ledger
        self._clob = None

    def execute(self, order: OrderRequest) -> Fill:
        fill = Fill.simulated(order) if self._settings.dry_run else self._place_live_order(order)
        self._ledger.record(fill)
        return fill

    def _clob_client(self):
        if self._clob is None:
            from py_clob_client.client import ClobClient  # type: ignore

            self._clob = ClobClient(
                self._settings.clob_base_url,
                key=self._settings.polygon_private_key,
                chain_id=137,
                funder=self._settings.polymarket_funder,
            )
        return self._clob

    def _place_live_order(self, order: OrderRequest) -> Fill:
        # NOTE: written against the documented py-clob-client interface but
        # not exercised against a live order book. Confirm order/signature
        # construction against the installed py-clob-client version before
        # relying on this path with real funds.
        client = self._clob_client()
        shares = order.size_usd / order.price
        signed_order = client.create_order(
            {
                "token_id": order.token_id,
                "price": order.price,
                "size": shares,
                "side": "BUY",
            }
        )
        response = client.post_order(signed_order)
        return Fill.live(order, response)
