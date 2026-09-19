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

    @property
    def hours_to_resolution(self) -> float:
        delta = self.end_date - datetime.now(timezone.utc)
        return delta.total_seconds() / 3600.0


class GammaClient:
    """Read-only access to Polymarket's Gamma API for market discovery and
    resolution status. No auth required."""

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
    )
