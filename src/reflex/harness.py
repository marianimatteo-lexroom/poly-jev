from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from . import edge_engine, reconcile, risk_manager
from .config import Settings, load_settings
from .executor import Executor, OrderRequest
from .jev_client import JevClient
from .ledger import Ledger
from .polymarket_client import GammaClient

logger = logging.getLogger("reflex")


class Reflex:
    """Reflex: a short-horizon yes/no trading agent for Polymarket.

    Its only goal is making money: scan short-horizon binary markets, ask
    Jev for a fair-value probability on each, and trade the gap against the
    market price whenever the edge, confidence, and risk limits all clear.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.gamma = GammaClient(self.settings)
        self.jev = JevClient(self.settings)
        self.ledger = Ledger(self.settings.ledger_path)
        self.executor = Executor(self.settings, self.ledger)

    def run_once(self) -> list[OrderRequest]:
        markets = self.gamma.fetch_active_binary_markets(self.settings.max_markets_per_cycle)
        candidates = [m for m in markets if self._in_horizon(m)]
        logger.info("scanned %d markets, %d in short-horizon window", len(markets), len(candidates))

        realized_pnl = reconcile.realized_pnl_since(self.ledger, self.gamma, _start_of_day_utc_ts())
        daily_loss = max(0.0, -realized_pnl)

        placed: list[OrderRequest] = []
        for market in candidates:
            try:
                signal = edge_engine.evaluate_market(self.jev, self.settings, market)
            except Exception:
                logger.exception("jev evaluation failed for %s", market.condition_id)
                continue

            if signal is None:
                continue

            size = risk_manager.size_trade(self.settings, self.ledger, signal, daily_loss)
            if size <= 0:
                continue

            token_id = market.yes_token_id if signal.side == "YES" else market.no_token_id
            price = market.yes_price if signal.side == "YES" else market.no_price
            order = OrderRequest(
                condition_id=market.condition_id,
                question=market.question,
                side=signal.side,
                token_id=token_id,
                price=price,
                size_usd=size,
            )
            self.executor.execute(order)
            placed.append(order)
            logger.info(
                "placed %s $%.2f @ %.3f (fair=%.3f edge=%.3f conf=%.2f) — %s",
                order.side,
                order.size_usd,
                order.price,
                signal.fair_probability,
                signal.edge,
                signal.confidence,
                market.question,
            )

        return placed

    def _in_horizon(self, market) -> bool:
        hours = market.hours_to_resolution
        return self.settings.min_hours_to_resolution <= hours <= self.settings.max_hours_to_resolution

    def run_forever(self) -> None:
        logger.info(
            "Reflex starting — dry_run=%s bankroll=$%.2f", self.settings.dry_run, self.settings.bankroll_usd
        )
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("cycle failed")
            time.sleep(self.settings.scan_interval_seconds)


def _start_of_day_utc_ts() -> float:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()
