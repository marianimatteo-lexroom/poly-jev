from __future__ import annotations

from reflex.polymarket_client import _parse_binary_market


def _raw_market(**overrides) -> dict:
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


def test_rejects_non_binary_outcomes():
    market = _parse_binary_market(_raw_market(outcomes='["Yes", "No", "Maybe"]'))
    assert market is None


def test_rejects_missing_token_ids():
    market = _parse_binary_market(_raw_market(clobTokenIds=None))
    assert market is None


def test_rejects_missing_end_date():
    market = _parse_binary_market(_raw_market(endDate=None))
    assert market is None
