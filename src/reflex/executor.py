from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings
from .ledger import Fill, Ledger


class ExecutorError(RuntimeError):
    pass


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

    Uses Polymarket's current official `polymarket-client` SDK, not the
    deprecated `py-clob-client` — that package targets contracts and a
    collateral token (USDC.e direct) that Polymarket's own docs list as
    replaced by pUSD and a new CTF Exchange (confirmed 2026-09-19 against
    docs.polymarket.com/resources/contracts and the SDK migration guide).
    `SecureClient.place_limit_order` resolves tick size, neg-risk status,
    and any missing token allowance itself — there's no separate manual
    approval step needed here.
    """

    def __init__(self, settings: Settings, ledger: Ledger):
        self._settings = settings
        self._ledger = ledger
        self._client = None

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

    def _secure_client(self):
        if self._client is None:
            from polymarket import SecureClient

            if not self._settings.polygon_private_key:
                raise ExecutorError("POLYGON_WALLET_PRIVATE_KEY is not set — cannot sign live orders")

            self._client = SecureClient.create(
                private_key=self._settings.polygon_private_key,
                wallet=self._settings.polymarket_funder or None,
            )
        return self._client

    def _place_live_order(self, order: OrderRequest) -> Fill:
        from polymarket.models.clob.order_response import RejectedOrder

        client = self._secure_client()
        shares = round(order.size_usd / order.price, 2)

        response = client.place_limit_order(
            token_id=order.token_id,
            price=order.price,
            size=shares,
            side="BUY",
        )
        if isinstance(response, RejectedOrder):
            raise ExecutorError(f"order rejected: {response.code} — {response.message}")

        return Fill.live(order, response.model_dump(mode="json"))
