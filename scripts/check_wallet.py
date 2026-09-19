from __future__ import annotations

import argparse
import sys

from reflex.config import load_settings
from reflex.onboarding import check_wallet


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only wallet check: pUSD (Polymarket's trading collateral) and MATIC "
        "balance. Needs only a public address — never a private key."
    )
    parser.add_argument(
        "--address",
        help="Wallet address to check. Defaults to POLYMARKET_FUNDER_ADDRESS from the environment.",
    )
    args = parser.parse_args()

    settings = load_settings()
    address = args.address or settings.polymarket_funder
    if not address:
        print("Pass --address or set POLYMARKET_FUNDER_ADDRESS in your .env", file=sys.stderr)
        raise SystemExit(1)

    status = check_wallet(settings, address)

    print(f"Wallet: {status.address}")
    print(f"  pUSD:  {status.pusd_balance:,.2f}  (Polymarket's trading collateral)")
    print(f"  MATIC: {status.matic_balance:,.4f} (for gas)")
    print()
    if status.ready_to_trade:
        print("Ready to trade.")
    elif status.pusd_balance == 0:
        print(
            "No pUSD yet. Deposit through polymarket.com with this wallet connected — "
            "that's the safest way to get USDC converted into pUSD correctly. "
            "See README for why we don't do this step for you."
        )
    else:
        print("Has pUSD but no MATIC for gas — fund it with a small amount of MATIC.")


if __name__ == "__main__":
    main()
