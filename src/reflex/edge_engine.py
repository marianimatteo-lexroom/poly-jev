from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .jev_client import JevClient, Noul
from .polymarket_client import BinaryMarket


@dataclass(frozen=True)
class TradeSignal:
    market: BinaryMarket
    side: str  # "YES" or "NO"
    fair_probability: float
    market_price: float
    edge: float
    confidence: float


def build_state(market: BinaryMarket) -> dict:
    """The context handed to Jev for a single market.

    This only includes the market's own metadata. For real edge you'd want
    to enrich this with retrieved context (news, related markets, order
    book depth) — this is the boundary where that plugs in.
    """
    return {
        "question": market.question,
        "market_yes_price": round(market.yes_price, 4),
        "hours_to_resolution": round(market.hours_to_resolution, 2),
        "liquidity_usd": round(market.liquidity_usd, 2),
        "volume_usd": round(market.volume_usd, 2),
    }


def evaluate_market(client: JevClient, settings: Settings, market: BinaryMarket) -> TradeSignal | None:
    """Asks Jev for a fair-value probability and a manipulation-risk flag,
    then decides whether the gap to the market price is worth trading.

    Returns None when there's no trade: manipulation risk too high or
    edge too small. Confidence (1 - risk) is recorded on the signal for
    logging only — it is not a second gate.
    """
    state = build_state(market)
    response = client.ask(
        state=state,
        questions={
            "resolves_yes": Noul(
                instructions=(
                    "Given everything you know about the world and the state "
                    "provided, estimate the true probability that this market "
                    "resolves YES. Ignore the current market price — judge the "
                    "underlying question on its merits."
                )
            ),
            "manipulation_risk": Noul(
                instructions=(
                    "There are signs this market is thinly traded, manipulated, "
                    "or otherwise unsafe to trade right now: ambiguous "
                    "resolution criteria, liquidity that's very low relative to "
                    "volume, or a question that looks already effectively "
                    "decided but mispriced due to inattention."
                )
            ),
        },
    )

    fair_p = response.nouls["resolves_yes"].noul
    risk = response.nouls["manipulation_risk"].noul
    if risk > settings.max_manipulation_risk:
        return None

    market_p = market.yes_price
    edge_yes = fair_p - market_p

    if edge_yes >= settings.min_edge:
        side, edge = "YES", edge_yes
    elif -edge_yes >= settings.min_edge:
        side, edge = "NO", -edge_yes
    else:
        return None

    return TradeSignal(
        market=market,
        side=side,
        fair_probability=fair_p,
        market_price=market_p,
        edge=edge,
        confidence=1.0 - risk,
    )
