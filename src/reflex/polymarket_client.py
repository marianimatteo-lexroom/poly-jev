from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from .config import Settings


@dataclass(frozen=True)
class BinaryMarket:
    condition_id: str
    question: str
    slug: str
    end_date: datetime
    yes_price: float
    no_price: float
    liquidity_usd: float
    volume_usd: float
    yes_token_id: str
    no_token_id: str
    tick_size: float
    min_order_size: float
    # Gamma's `restricted` flag is undocumented and was `true` on 100/100
    # markets sampled while building this — it has no discriminative value,
    # so it's captured but never filtered on. Check Polymarket's terms and
    # your own jurisdiction's legal status yourself before trading live.
    restricted: bool
    neg_risk: bool

    @property
    def hours_to_resolution(self) -> float:
        delta = self.end_date - datetime.now(timezone.utc)
        return delta.total_seconds() / 3600.0


class GammaClient:
    """Read-only access to Polymarket's Gamma API for market discovery and
    resolution status. No auth required.

    Schema verified live against https://gamma-api.polymarket.com on
    2026-09-19 — field names below (outcomes, outcomePrices, clobTokenIds,
    liquidityNum, volumeNum, orderPriceMinTickSize, orderMinSize, restricted)
    match a real market response, not just documentation.
    """

    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()

    def fetch_active_binary_markets(self, limit: int) -> list[BinaryMarket]:
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "order": "volume24hr",
            "ascending": "false",
        }
        resp = self._session.get(f"{self._settings.gamma_base_url}/markets", params=params, timeout=15)
        resp.raise_for_status()

        markets = []
        for raw in resp.json():
            market = _parse_binary_market(raw)
            if market is not None:
                markets.append(market)
        return markets

    def fetch_resolution(self, condition_id: str) -> str | None:
        """Returns "YES" or "NO" once a market has settled, else None."""
        resp = self._session.get(
            f"{self._settings.gamma_base_url}/markets",
            params={"condition_ids": condition_id},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None

        raw = results[0]
        if not raw.get("closed"):
            return None

        prices = _maybe_parse_json(raw.get("outcomePrices"))
        if not prices:
            return None

        yes_price = float(prices[0])
        if yes_price >= 0.99:
            return "YES"
        if yes_price <= 0.01:
            return "NO"
        return None


class ClobMarketData:
    """Read-only access to Polymarket's public CLOB endpoints — no auth
    required. Verified live against https://clob.polymarket.com on
    2026-09-19 (/price, /book, /tick-size all confirmed reachable and
    correctly shaped against a real token id).

    Used to get an executable price right before sizing/placing an order,
    since the Gamma `yes_price`/`no_price` snapshot can be stale, and to
    mark open positions to market for the daily-loss kill switch.
    """

    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()

    def get_price(self, token_id: str, side: str) -> float | None:
        resp = self._session.get(
            f"{self._settings.clob_base_url}/price",
            params={"token_id": token_id, "side": side},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        return float(resp.json()["price"])

    def get_best_bid(self, token_id: str) -> float | None:
        return self.get_price(token_id, "SELL")

    def get_best_ask(self, token_id: str) -> float | None:
        return self.get_price(token_id, "BUY")


def _maybe_parse_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _parse_binary_market(raw: dict[str, Any]) -> BinaryMarket | None:
    outcomes = _maybe_parse_json(raw.get("outcomes"))
    if outcomes != ["Yes", "No"]:
        return None

    prices = _maybe_parse_json(raw.get("outcomePrices"))
    if not prices or len(prices) != 2:
        return None

    token_ids = _maybe_parse_json(raw.get("clobTokenIds"))
    if not token_ids or len(token_ids) != 2:
        return None

    end_date_raw = raw.get("endDate")
    if not end_date_raw:
        return None

    condition_id = raw.get("conditionId")
    if not condition_id:
        return None

    return BinaryMarket(
        condition_id=condition_id,
        question=raw.get("question", ""),
        slug=raw.get("slug", ""),
        end_date=datetime.fromisoformat(end_date_raw.replace("Z", "+00:00")),
        yes_price=float(prices[0]),
        no_price=float(prices[1]),
        liquidity_usd=float(raw.get("liquidityNum", raw.get("liquidity", 0)) or 0),
        volume_usd=float(raw.get("volumeNum", raw.get("volume", 0)) or 0),
        yes_token_id=str(token_ids[0]),
        no_token_id=str(token_ids[1]),
        tick_size=float(raw.get("orderPriceMinTickSize", 0.01) or 0.01),
        min_order_size=float(raw.get("orderMinSize", 5) or 5),
        restricted=bool(raw.get("restricted", False)),
        neg_risk=bool(raw.get("negRisk", False)),
    )
