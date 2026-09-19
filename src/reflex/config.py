from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # Jev / TypeSafe
    typesafe_api_key: str = field(default_factory=lambda: _env_str("TYPESAFE_API_KEY", ""))
    jev_model: str = field(default_factory=lambda: _env_str("JEV_MODEL", "jev-latest"))
    typesafe_base_url: str = field(
        default_factory=lambda: _env_str("TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1/systemone")
    )

    # Polymarket
    gamma_base_url: str = field(default_factory=lambda: _env_str("GAMMA_BASE_URL", "https://gamma-api.polymarket.com"))
    clob_base_url: str = field(default_factory=lambda: _env_str("CLOB_BASE_URL", "https://clob.polymarket.com"))
    polygon_private_key: str = field(default_factory=lambda: _env_str("POLYGON_WALLET_PRIVATE_KEY", ""))
    polymarket_funder: str = field(default_factory=lambda: _env_str("POLYMARKET_FUNDER_ADDRESS", ""))

    # Safety / mode — refuse to trade for real unless explicitly told to.
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", True))

    # Universe filters — what counts as "short horizon".
    min_hours_to_resolution: float = field(default_factory=lambda: _env_float("MIN_HOURS_TO_RESOLUTION", 0.5))
    max_hours_to_resolution: float = field(default_factory=lambda: _env_float("MAX_HOURS_TO_RESOLUTION", 48.0))
    min_liquidity_usd: float = field(default_factory=lambda: _env_float("MIN_LIQUIDITY_USD", 2000.0))
    min_volume_usd: float = field(default_factory=lambda: _env_float("MIN_VOLUME_USD", 5000.0))

    # Edge / decision thresholds.
    min_edge: float = field(default_factory=lambda: _env_float("MIN_EDGE", 0.05))
    min_edge_confidence: float = field(default_factory=lambda: _env_float("MIN_EDGE_CONFIDENCE", 0.6))
    max_manipulation_risk: float = field(default_factory=lambda: _env_float("MAX_MANIPULATION_RISK", 0.35))

    # Risk / sizing.
    bankroll_usd: float = field(default_factory=lambda: _env_float("BANKROLL_USD", 1000.0))
    kelly_fraction: float = field(default_factory=lambda: _env_float("KELLY_FRACTION", 0.25))
    max_position_usd: float = field(default_factory=lambda: _env_float("MAX_POSITION_USD", 50.0))
    max_position_fraction: float = field(default_factory=lambda: _env_float("MAX_POSITION_FRACTION", 0.05))
    max_open_positions: int = field(default_factory=lambda: _env_int("MAX_OPEN_POSITIONS", 15))
    max_daily_loss_usd: float = field(default_factory=lambda: _env_float("MAX_DAILY_LOSS_USD", 100.0))
    max_market_exposure_usd: float = field(default_factory=lambda: _env_float("MAX_MARKET_EXPOSURE_USD", 50.0))

    # Loop cadence.
    scan_interval_seconds: int = field(default_factory=lambda: _env_int("SCAN_INTERVAL_SECONDS", 300))
    max_markets_per_cycle: int = field(default_factory=lambda: _env_int("MAX_MARKETS_PER_CYCLE", 200))

    ledger_path: str = field(default_factory=lambda: _env_str("LEDGER_PATH", "data/ledger.jsonl"))


def load_settings() -> Settings:
    return Settings()
