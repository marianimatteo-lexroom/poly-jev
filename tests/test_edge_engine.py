from __future__ import annotations

from dataclasses import dataclass

import pytest
from factories import make_market

from reflex import edge_engine
from reflex.config import Settings


@dataclass(frozen=True)
class _FakeNoulAnswer:
    noul: float


@dataclass(frozen=True)
class _FakeResponse:
    nouls: dict[str, _FakeNoulAnswer]


class FakeJevClient:
    """Stands in for `reflex.jev_client.JevClient`, matching the shape of
    the real `typesafe_sdk.SystemOneResponse` (`.nouls[key].noul`) that
    `edge_engine.evaluate_market` actually reads — verified against the
    real SDK in `jev_client.py`, not guessed here."""

    def __init__(self, resolves_yes: float, manipulation_risk: float):
        self._resolves_yes = resolves_yes
        self._manipulation_risk = manipulation_risk
        self.calls: list[tuple] = []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        return _FakeResponse(
            nouls={
                "resolves_yes": _FakeNoulAnswer(self._resolves_yes),
                "manipulation_risk": _FakeNoulAnswer(self._manipulation_risk),
            }
        )


def default_settings(**overrides) -> Settings:
    base = dict(min_edge=0.05, max_manipulation_risk=0.35)
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


def test_does_not_gate_on_derived_confidence():
    """Risk of 0.3 is under max_manipulation_risk=0.35, so the trade proceeds.
    Derived confidence (1 - risk = 0.7) is recorded for logging and is not a
    second gate — previously a duplicate confidence threshold would have skipped
    this signal."""
    market = make_market(yes_price=0.40)
    client = FakeJevClient(resolves_yes=0.60, manipulation_risk=0.3)
    settings = default_settings()

    signal = edge_engine.evaluate_market(client, settings, market)

    assert signal is not None
    assert signal.side == "YES"
    assert signal.confidence == pytest.approx(0.7)
