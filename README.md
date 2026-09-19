# Reflex

Reflex is a short-horizon yes/no trading agent for [Polymarket](https://polymarket.com), built as a harness around [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev), TypeSafe AI's "System One" model. Its only goal is making money: it scans binary markets resolving soon, prices each one against Jev's estimate, and trades the gap.

## Why Jev

Jev doesn't generate text — it evaluates a state and returns typed decisions (a choice, a score, or a yes/no probability) in a single parallel pass, reportedly 100-200x faster and far cheaper per question than calling a full LLM (see [TypeSafe's launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev) and [Sydney Runkle's harness writeup](https://www.langchain.com/blog/building-a-harness-with-jev), Sept 2026). That's the right shape for a loop that needs to re-price hundreds of markets a minute: Reflex asks Jev one `noul` (yes/no probability) question per market — *"what's the true probability this resolves YES"* — plus a `manipulation_risk` question to screen out unsafe markets, and trades the gap between Jev's answer and the market's implied price.

Reflex is the harness — scanning, context-building, sizing, execution, bookkeeping. Jev only answers the probability question; it never sees an order book or touches a wallet.

## Architecture

```
GammaClient   -> discover active binary (Yes/No) markets, filter to short horizon
edge_engine   -> ask Jev: fair probability + manipulation-risk per market
risk_manager  -> fractional-Kelly position sizing, exposure & loss caps
Executor      -> paper-trade (default) or place a live CLOB order
Ledger        -> append-only trade log; reconcile.py computes realized PnL
Reflex        -> orchestrates the scan -> decide -> size -> execute loop
```

## Safety defaults

- **`DRY_RUN=true` by default.** Every "trade" is logged to `data/ledger.jsonl`; nothing is ever sent to Polymarket until you explicitly set `DRY_RUN=false` *and* supply a funded wallet key.
- Hard caps on position size, per-market exposure, open position count, and daily realized loss (`risk_manager.py`) — these gate every order before it's placed, regardless of what Kelly sizing would otherwise suggest.
- A `manipulation_risk` Jev question screens out thin, ambiguous, or already-decided-but-mispriced markets before sizing even runs.
- Fractional Kelly (`KELLY_FRACTION`, default `0.25`) rather than full Kelly, since Jev's calibration is the real bottleneck on edge quality, not the sizing math.

**This is a harness, not investment advice.** Prediction markets involve real money and real loss; Reflex's edge is only as good as Jev's calibration on markets it was never trained to see, and the `state` it builds today (`edge_engine.build_state`) is just the market's own metadata — no live news feed. Read the code before turning off `DRY_RUN`.

## Setup

```bash
pip install -e ".[dev]"      # add "[live]" too once you're ready to trade for real
cp .env.example .env         # fill in TYPESAFE_API_KEY at minimum
pytest                       # decision-logic tests only, no network calls
python scripts/run.py --once # one scan-and-trade cycle, paper mode by default
```

To go live: set `DRY_RUN=false`, `POLYGON_WALLET_PRIVATE_KEY`, and `POLYMARKET_FUNDER_ADDRESS` in `.env`, fund the wallet with USDC on Polygon, and install the `live` extra (`py-clob-client`). `executor.py`'s order construction is written against the documented `py-clob-client` interface but hasn't been exercised against a live order book — confirm it against the installed package version before relying on it with real funds.

## Configuration

Everything is an environment variable — see `.env.example` for the full list and defaults: universe filters (what counts as "short horizon"), edge/confidence thresholds, and risk limits (bankroll, Kelly fraction, position/exposure/loss caps).

## Extending the edge

Jev's `noul` question only reasons over whatever `state` you hand it. Today that's just the market's question text, price, liquidity, volume, and time to resolution — there's no retrieval of news or related markets. Real edge comes from enriching `edge_engine.build_state()` before the `evaluate_market()` call, and possibly adding more Jev questions (e.g. a `Choice` between "priced correctly / underpriced / overpriced / can't tell") to route only the ambiguous cases into a slower, more expensive research pass. The `JevClient` also exposes `choice()` and `score()` helpers, not just `noul()`, for that.

## Disclaimer

Not financial advice. Trading on Polymarket may be restricted or illegal in your jurisdiction — check local regulations before enabling live trading. You are responsible for any funds this agent trades.
