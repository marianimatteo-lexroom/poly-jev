from __future__ import annotations

import argparse

from reflex.config import load_settings
from reflex.onboarding import check_wallet, ensure_approvals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send whichever USDC/CTF approval transactions Polymarket's CLOB needs that "
        "your wallet doesn't already have. Requires POLYGON_WALLET_PRIVATE_KEY and MATIC for gas."
    )
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.polygon_private_key:
        raise SystemExit("POLYGON_WALLET_PRIVATE_KEY is not set — see README for where this comes from.")

    from web3 import Web3

    address = Web3().eth.account.from_key(settings.polygon_private_key).address
    status = check_wallet(settings, address)

    print(f"Wallet: {status.address}")
    print(f"  USDC:  {status.usdc_balance:,.2f}")
    print(f"  MATIC: {status.matic_balance:,.4f} (for gas)")
    if status.ready_to_trade:
        print("Already fully approved — nothing to send.")
        return

    if status.matic_balance <= 0:
        raise SystemExit("Wallet has no MATIC for gas — fund it before running this.")

    missing = [e.label for e in status.exchanges if not e.ready]
    print(f"Missing approvals for: {', '.join(missing)}")

    if not args.yes:
        confirm = input("Send approval transactions now? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    tx_hashes = ensure_approvals(settings)
    for tx_hash in tx_hashes:
        print(f"Sent: https://polygonscan.com/tx/{tx_hash}")
    print(f"Done — sent {len(tx_hashes)} transaction(s). Re-run scripts/check_wallet.py once confirmed.")


if __name__ == "__main__":
    main()
