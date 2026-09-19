from __future__ import annotations

import argparse
import sys

from reflex.config import load_settings
from reflex.onboarding import check_wallet


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only wallet check: USDC/MATIC balance and Polymarket exchange approvals. "
        "Needs only a public address — never a private key."
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
    print(f"  USDC:  {status.usdc_balance:,.2f}")
    print(f"  MATIC: {status.matic_balance:,.4f} (for gas)")
    for exchange in status.exchanges:
        state = "ready" if exchange.ready else "NOT ready"
        print(f"  [{exchange.label}] {exchange.exchange_address} — {state}")
        print(f"      USDC allowance: {exchange.usdc_allowance}")
        print(f"      CTF approved:   {exchange.ctf_approved}")

    print()
    if status.ready_to_trade:
        print("Ready to trade.")
    else:
        print("Not ready yet. Run scripts/onboard_wallet.py to send the missing approvals.")


if __name__ == "__main__":
    main()
