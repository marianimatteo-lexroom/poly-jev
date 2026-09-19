from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings
from .ledger import Fill, Ledger


class ExecutorError(RuntimeError):
    pass


_VALID_TICK_SIZES = ("0.1", "0.01", "0.001", "0.0001")


def _tick_size_str(value: float) -> str:
    """py-clob-client's PartialCreateOrderOptions.tick_size is typed as one
    of these four literal strings, not a float — Gamma reports it as a
    float (e.g. 0.01), so this bridges the two."""
    candidate = f"{value:g}"
    return candidate if candidate in _VALID_TICK_SIZES else "0.01"


@dataclass(frozen=True)
class OrderRequest:
    condition_id: str
    question: str
    side: Literal["YES", "NO"]
    token_id: str
    price: float
    size_usd: float
    tick_size: float
    min_order_size: float
    neg_risk: bool


class Executor:
    """Places (or simulates) orders. Defaults to paper trading — a live
    order is only ever sent when `settings.dry_run` is explicitly False.

    Live order construction verified against the real `py-clob-client`
    0.34.6 API (installed and inspected on 2026-09-19): `ClobClient.__init__`,
    `OrderArgs`, `OrderType`, and the Level 1 (signing) / Level 2 (posting)
    auth split below all match the installed package's actual signatures —
    this was not exercised against a live order book, since that needs a
    funded wallet.
    """

    def __init__(self, settings: Settings, ledger: Ledger):
        self._settings = settings
        self._ledger = ledger
        self._clob = None

    def execute(self, order: OrderRequest) -> Fill:
        if order.size_usd < order.min_order_size * order.price:
            raise ExecutorError(
                f"order size ${order.size_usd:.2f} is below this market's minimum "
                f"({order.min_order_size} shares @ {order.price:.3f} "
                f"= ${order.min_order_size * order.price:.2f})"
            )

        fill = Fill.simulated(order) if self._settings.dry_run else self._place_live_order(order)
        self._ledger.record(fill)
        return fill

    def _clob_client(self):
        if self._clob is None:
            from py_clob_client.client import ClobClient

            if not self._settings.polygon_private_key:
                raise ExecutorError("POLYGON_WALLET_PRIVATE_KEY is not set — cannot sign live orders")

            client = ClobClient(
                self._settings.clob_base_url,
                key=self._settings.polygon_private_key,
                chain_id=137,
                funder=self._settings.polymarket_funder or None,
                signature_type=self._settings.polymarket_signature_type,
            )
            # Level 2 auth (posting orders) needs API creds derived from the
            # signing key; `create_or_derive_api_creds` creates them the
            # first time and re-derives the same ones on every call after.
            client.set_api_creds(client.create_or_derive_api_creds())
            self._clob = client
        return self._clob

    def _place_live_order(self, order: OrderRequest) -> Fill:
        from py_clob_client.clob_types import OrderArgs, OrderType, PartialCreateOrderOptions
        from py_clob_client.order_builder.constants import BUY

        client = self._clob_client()
        shares = round(order.size_usd / order.price, 2)

        order_args = OrderArgs(
            token_id=order.token_id,
            price=order.price,
            size=shares,
            side=BUY,
        )
        signed_order = client.create_order(
            order_args,
            PartialCreateOrderOptions(tick_size=_tick_size_str(order.tick_size), neg_risk=order.neg_risk),
        )
        response = client.post_order(signed_order, OrderType.GTC)
        return Fill.live(order, response)
