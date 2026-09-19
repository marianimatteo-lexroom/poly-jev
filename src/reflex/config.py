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
    # Jev / TypeSafe. Only the key is read here — TypeSafeClient manages
    # TYPESAFE_BASE_URL / TYPESAFE_DEFAULT_MODEL itself (see jev_client.py).
    typesafe_api_key: str = field(default_factory=lambda: _env_str("TYPESAFE_API_KEY", ""))

    # Polymarket
    gamma_base_url: str = field(default_factory=lambda: _env_str("GAMMA_BASE_URL", "https://gamma-api.polymarket.com"))
    clob_base_url: str = field(default_factory=lambda: _env_str("CLOB_BASE_URL", "https://clob.polymarket.com"))
    # polygon-rpc.com and several other "free public" RPCs returned 401s
    # (disabled/gated) when this was tested on 2026-09-19 — this one
    # actually worked, verified live. Swap it if it stops working for you.
    polygon_rpc_url: str = field(
        default_factory=lambda: _env_str("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
    )
    polygon_private_key: str = field(default_factory=lambda: _env_str("POLYGON_WALLET_PRIVATE_KEY", ""))
    polymarket_funder: str = field(default_factory=lambda: _env_str("POLYMARKET_FUNDER_ADDRESS", ""))
    # 0 = EOA (you trade directly from the private key's own address).
    # 1 = email/magic-link wallet proxy. 2 = browser-wallet (Gnosis Safe) proxy.
    # Polymarket UI signups default to a proxy wallet (1 or 2) — see README.
    polymarket_signature_type: int = field(default_factory=lambda: _env_int("POLYMARKET_SIGNATURE_TYPE", 0))

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
