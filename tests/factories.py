from __future__ import annotations

from datetime import datetime, timedelta, timezone

from reflex.polymarket_client import BinaryMarket


def make_market(
    yes_price: float = 0.5,
    hours: float = 24.0,
    liquidity: float = 10_000,
    volume: float = 20_000,
    condition_id: str = "0xabc",
) -> BinaryMarket:
    return BinaryMarket(
        condition_id=condition_id,
        question="Will it happen?",
        slug="will-it-happen",
        end_date=datetime.now(timezone.utc) + timedelta(hours=hours),
        yes_price=yes_price,
        no_price=1 - yes_price,
        liquidity_usd=liquidity,
        volume_usd=volume,
        yes_token_id="yes-token",
        no_token_id="no-token",
    )
