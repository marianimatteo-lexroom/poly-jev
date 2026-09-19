from __future__ import annotations

import pytest
from factories import make_market

from reflex import edge_engine
from reflex.config import Settings
from reflex.jev_client import Answer, JevResponse


class FakeJevClient:
    def __init__(self, resolves_yes: float, manipulation_risk: float):
        self._resolves_yes = resolves_yes
        self._manipulation_risk = manipulation_risk
        self.calls: list[tuple] = []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        return JevResponse(
            model="jev-test",
            answers={
                "resolves_yes": Answer({"noul": self._resolves_yes}),
                "manipulation_risk": Answer({"noul": self._manipulation_risk}),
            },
        )


def default_settings(**overrides) -> Settings:
    base = dict(min_edge=0.05, min_edge_confidence=0.6, max_manipulation_risk=0.35)
    base.update(overrides)
    return Settings(**base)


def test_evaluates_yes_edge_when_underpriced():
    market = make_market(yes_price=0.40)
    client = FakeJevClient(resolves_yes=0.60, manipulation_risk=0.1)
    settings = default_settings()

    signal = edge_engine.evaluate_market(client, settings, market)

    assert signal is not None
    assert signal.side == "YES"
    assert signal.edge == pytest.approx(0.20)
    assert signal.confidence == pytest.approx(0.9)


def test_evaluates_no_edge_when_overpriced():
    market = make_market(yes_price=0.85)
    client = FakeJevClient(resolves_yes=0.55, manipulation_risk=0.1)
    settings = default_settings()

    signal = edge_engine.evaluate_market(client, settings, market)

    assert signal is not None
    assert signal.side == "NO"
    assert signal.edge == pytest.approx(0.30)


def test_skips_when_edge_too_small():
    market = make_market(yes_price=0.50)
    client = FakeJevClient(resolves_yes=0.52, manipulation_risk=0.1)
    settings = default_settings()

    assert edge_engine.evaluate_market(client, settings, market) is None


def test_skips_when_manipulation_risk_too_high():
    market = make_market(yes_price=0.40)
    client = FakeJevClient(resolves_yes=0.60, manipulation_risk=0.9)
    settings = default_settings()

    assert edge_engine.evaluate_market(client, settings, market) is None


def test_skips_when_confidence_too_low():
    market = make_market(yes_price=0.40)
    client = FakeJevClient(resolves_yes=0.60, manipulation_risk=0.3)
    settings = default_settings(min_edge_confidence=0.75)

    assert edge_engine.evaluate_market(client, settings, market) is None
