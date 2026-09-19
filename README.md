# Reflex

Reflex is a short-horizon yes/no trading agent for [Polymarket](https://polymarket.com), built as a harness around [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev), TypeSafe AI's "System One" model. Its only goal is making money: it scans binary markets resolving soon, prices each one against Jev's estimate, and trades the gap.

## Why Jev

Jev doesn't generate text — it evaluates a state and returns typed decisions (a choice, a score, or a yes/no probability) in a single parallel pass, reportedly 100-200x faster and far cheaper per question than calling a full LLM (TypeSafe AI, Sept 2026). Reflex asks Jev one `Noul` (yes/no probability) question per market — *"what's the true probability this resolves YES"* — plus a `manipulation_risk` question, and trades the gap between Jev's answer and the market's implied price.

## What's actually verified vs. what still needs your key

Everything below was confirmed by hitting the real, live services while building this — not assumed from documentation:

| Component | Status |
|---|---|
| Gamma API market schema (`polymarket_client.py`) | **Verified live** against `gamma-api.polymarket.com` — field names, types, `restricted`/`negRisk`/tick-size/min-order-size all confirmed on real markets |
| Public CLOB price/book endpoints | **Verified live** — `/price`, `/book`, `/tick-size` all confirmed reachable, no auth needed |
| Jev request/response shape (`jev_client.py`) | **Verified live**, using the real `typesafe-sdk` PyPI package — confirmed the full request round-trip against `api.typesafe.ai`, including a real successful `Noul` answer with a live key |
| Order execution (`executor.py`) | **Verified against Polymarket's current official SDK, `polymarket-client`** — real request construction confirmed by inspecting the installed package (0.10.0). Not exercised against a live fill — that needs a funded wallet |
| Wallet balance check (`onboarding.py`) | **Verified live** — reads pUSD (Polymarket's current collateral token) and MATIC balance for a real address with no private key needed |
| Mark-to-market risk (`reconcile.py`) | Implemented and unit-tested; open positions are priced against the live CLOB bid, not just resolved-market PnL |

**Two corrections made after the first pass, both worth knowing about:**

1. Gamma's `restricted` field looked like a useful "skip risky markets" safety filter, but it's `true` on 100% of the top 100 markets by volume — it's not a market-quality signal, and filtering on it made the scanner find nothing. It's captured on `BinaryMarket` but no longer filtered. **Check Polymarket's terms and your own jurisdiction's legal status yourself** — this flag doesn't tell you anything useful about that.
2. The first version of `executor.py`/`onboarding.py` was built and verified against `py-clob-client` — which turned out to be a **deprecated** package. Polymarket has since moved to an official unified SDK (`polymarket-client`) and a new collateral token, **pUSD** (replacing direct USDC.e), with new exchange contract addresses. The old code was internally consistent and "verified" against that legacy stack, which is exactly why this is worth calling out explicitly: verifying against a real API doesn't catch it having been superseded. Both files were rewritten against the current stack — see git history if you want the contrast.

**Because of #2: fund your wallet through polymarket.com's own deposit flow, not by sending raw USDC to the address and expecting this code to convert it.** Depositing correctly (native USDC or USDC.e → pUSD) is Polymarket's own UI's job; `check_wallet.py` only reads your resulting pUSD balance, it doesn't wrap anything for you.

## What I need from you

1. **A TypeSafe API key**, to get real Jev answers instead of the confirmed-but-empty request path above. Sign up at [typesafe.ai](https://typesafe.ai), create a key at **[console.typesafe.ai/keys](https://console.typesafe.ai/keys)**, put it in `.env` as `TYPESAFE_API_KEY`. Then run:
   ```bash
   python scripts/smoke_test_jev.py
   ```
   This makes one real call and prints the real response shape — worth running before trusting anything else here.

2. **If/when you want live trading** (optional — paper trading needs none of this): a Polygon wallet with a little MATIC for gas, deposited into **through polymarket.com directly** (connect the wallet there, use their deposit flow — it correctly converts your USDC into pUSD, which nothing in this repo does for you). **Never paste a private key into a chat with me or any AI assistant** — set `POLYGON_WALLET_PRIVATE_KEY` directly in your own `.env`. Then:
   ```bash
   python scripts/check_wallet.py --address 0xYourAddress   # read-only, no key needed — confirms pUSD landed
   ```
   There's no separate approval step to run — `polymarket-client` sets any missing token allowance itself the first time you place an order, using the same signing key. Set `POLYMARKET_FUNDER_ADDRESS` if your trading wallet differs from your signing key's own address (matches the old CLOB's "funder" concept); leave it unset otherwise.

## Architecture

```
GammaClient    -> discover active binary (Yes/No) markets
ClobMarketData -> live public price/book (no auth) for execution & mark-to-market
edge_engine    -> ask Jev: fair probability + manipulation-risk per market
risk_manager   -> fractional-Kelly sizing, exposure/loss caps
Executor       -> paper-trade (default) or place a live CLOB order
Ledger         -> append-only trade log
reconcile      -> realized PnL (resolved markets) + unrealized PnL (mark-to-market)
onboarding     -> read-only pUSD/MATIC balance check
Reflex         -> orchestrates the scan -> decide -> size -> execute loop
```

## Safety defaults

- **`DRY_RUN=true` by default.** Every "trade" is logged to `data/ledger.jsonl`; nothing is ever sent to Polymarket until you explicitly set `DRY_RUN=false` *and* supply a funded wallet key.
- Hard caps on position size, per-market exposure, open position count, and daily loss —**now including unrealized mark-to-market**, not just PnL from markets that have already resolved.
- A `manipulation_risk` Jev question screens out thin, ambiguous, or already-decided-but-mispriced markets.
- Orders below a market's real `orderMinSize` are rejected pre-flight rather than silently sent.
- Fractional Kelly (`KELLY_FRACTION`, default `0.25`).

**This is a harness, not investment advice.** Reflex's edge is only as good as Jev's calibration on markets it's never specifically been evaluated against, and `edge_engine.build_state()` today only feeds it the market's own metadata — no live news feed. Read the code before turning off `DRY_RUN`.

## Setup

```bash
pip install -e ".[dev]"        # add "[live]" too for polymarket-client + web3 (wallet/execution)
cp .env.example .env           # fill in TYPESAFE_API_KEY at minimum
pytest                         # decision logic + parsing, no network calls
python scripts/smoke_test_jev.py   # one real Jev call — needs your key
python scripts/run.py --once --verbose   # one scan-and-trade cycle, paper mode by default
```

## Configuration

Everything is an environment variable — see `.env.example` for the full list: universe filters (what counts as "short horizon"), edge/confidence thresholds, risk limits, and wallet/signature settings.

## Extending the edge

Jev's `Noul` question only reasons over whatever `state` you hand it — today that's the market's question text, price, liquidity, volume, and time to resolution, with no retrieval of news or related markets. Real edge comes from enriching `edge_engine.build_state()` before the `evaluate_market()` call. `JevClient` also exposes the real `Choice` and `Score` question types from `typesafe-sdk`, not just `Noul`, for routing ambiguous cases into a slower research pass.

## Known gaps

- `executor.py`'s live order path is verified for construction, not for an actual fill — confirm against your own account before trusting it with size.
- `reconcile.unrealized_pnl_since` prices at the best bid, which is conservative but not necessarily what you'd actually get selling into size.
- No process supervision beyond the top-level retry loop in `run_forever` — run it under something (systemd, a container restart policy) that will restart it if it dies.
- This stack (`polymarket-client`, pUSD, the current exchange contracts) was current as of 2026-09-19. Given Polymarket had already deprecated one full SDK generation by the time this was built, don't assume this stays current indefinitely — re-verify against `docs.polymarket.com` if things stop working.

## Disclaimer

Not financial advice. Trading on Polymarket may be restricted or illegal in your jurisdiction — check yourself, since (as noted above) the API's own `restricted` field won't tell you. You are responsible for any funds this agent trades.
