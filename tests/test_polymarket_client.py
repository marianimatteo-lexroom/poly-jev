from __future__ import annotations

from reflex.config import Settings
from reflex.polymarket_client import GammaClient, _parse_binary_market


def _raw_market(**overrides) -> dict:
    # Field names/shapes match a real response from
    # https://gamma-api.polymarket.com/markets, captured 2026-09-19 —
    # not just documentation.
    base = {
        "conditionId": "0xabc",
        "question": "Will BTC close above $100k today?",
        "slug": "btc-100k-today",
        "endDate": "2026-09-20T00:00:00Z",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.62", "0.38"]',
        "clobTokenIds": '["111", "222"]',
        "liquidityNum": 12000.5,
        "volumeNum": 45000.25,
        "orderPriceMinTickSize": 0.01,
        "orderMinSize": 5,
        "restricted": False,
        "negRisk": False,
    }
    base.update(overrides)
    return base


def test_parses_valid_binary_market():
    market = _parse_binary_market(_raw_market())

    assert market is not None
    assert market.condition_id == "0xabc"
    assert market.yes_price == 0.62
    assert market.no_price == 0.38
    assert market.yes_token_id == "111"
    assert market.no_token_id == "222"
    assert market.liquidity_usd == 12000.5
    assert market.tick_size == 0.01
    assert market.min_order_size == 5
    assert market.restricted is False
    assert market.neg_risk is False


def test_rejects_non_binary_outcomes():
    market = _parse_binary_market(_raw_market(outcomes='["Yes", "No", "Maybe"]'))
    assert market is None


def test_rejects_missing_token_ids():
    market = _parse_binary_market(_raw_market(clobTokenIds=None))
    assert market is None


def test_rejects_missing_end_date():
    market = _parse_binary_market(_raw_market(endDate=None))
    assert market is None


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload

    def get(self, url, params=None, timeout=None):
        return _FakeResponse(self._payload)


def test_gamma_client_does_not_filter_on_restricted_flag():
    # `restricted` was found true on 100/100 real markets sampled while
    # building this — filtering on it would make the scanner find nothing,
    # so it's captured on BinaryMarket but never used to exclude a market.
    payload = [_raw_market(conditionId="0x1", restricted=True), _raw_market(conditionId="0x2", restricted=False)]
    client = GammaClient(Settings(), session=_FakeSession(payload))

    markets = client.fetch_active_binary_markets(limit=10)

    assert {m.condition_id for m in markets} == {"0x1", "0x2"}
