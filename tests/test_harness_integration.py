from __future__ import annotations

from factories import make_market
from test_edge_engine import FakeJevClient

from reflex.config import Settings
from reflex.harness import Reflex


class FakeGamma:
    def __init__(self, markets):
        self._markets = markets

    def fetch_active_binary_markets(self, limit):
        return self._markets

    def fetch_resolution(self, condition_id):
        return None  # nothing resolved yet


class FakeClobData:
    def get_best_ask(self, token_id):
        return None  # forces fallback to the Gamma snapshot price

    def get_best_bid(self, token_id):
        return None


def test_run_once_places_a_paper_trade_end_to_end(tmp_path):
    market = make_market(yes_price=0.40, hours=12.0)
    settings = Settings(
        typesafe_api_key="fake-for-construction-only",
        dry_run=True,
        ledger_path=str(tmp_path / "ledger.jsonl"),
        min_hours_to_resolution=0.5,
        max_hours_to_resolution=48,
        min_liquidity_usd=0,
        min_volume_usd=0,
        min_edge=0.05,
        min_edge_confidence=0.6,
        max_manipulation_risk=0.35,
        bankroll_usd=1000,
        kelly_fraction=1.0,
        max_position_usd=50,
        max_daily_loss_usd=1000,
    )

    agent = Reflex(settings)
    agent.gamma = FakeGamma([market])
    agent.jev = FakeJevClient(resolves_yes=0.60, manipulation_risk=0.1)
    agent.clob_data = FakeClobData()

    placed = agent.run_once()

    assert len(placed) == 1
    assert placed[0].side == "YES"
    assert placed[0].condition_id == market.condition_id

    fills = agent.ledger.read_all()
    assert len(fills) == 1
    assert fills[0].mode == "paper"
