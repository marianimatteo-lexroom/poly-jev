from __future__ import annotations

import argparse
import logging

from reflex.harness import Reflex


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Reflex, the Jev-powered Polymarket trading agent.")
    parser.add_argument("--once", action="store_true", help="Run a single scan-and-trade cycle and exit.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    agent = Reflex()
    if args.once:
        agent.run_once()
    else:
        agent.run_forever()


if __name__ == "__main__":
    main()
