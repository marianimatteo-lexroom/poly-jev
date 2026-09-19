from __future__ import annotations

from reflex.config import load_settings
from reflex.jev_client import JevClient, Noul


def main() -> None:
    settings = load_settings()
    if not settings.typesafe_api_key:
        raise SystemExit(
            "TYPESAFE_API_KEY is not set. Create one at https://console.typesafe.ai/keys and put it in .env."
        )

    with JevClient(settings) as client:
        response = client.ask(
            state={
                "question": "Will the Fed cut interest rates at its next meeting?",
                "market_yes_price": 0.42,
                "hours_to_resolution": 18.0,
                "liquidity_usd": 50000,
                "volume_usd": 120000,
            },
            questions={
                "resolves_yes": Noul(
                    instructions="Estimate the true probability this resolves YES, ignoring the market price."
                ),
                "manipulation_risk": Noul(
                    instructions="There are signs this market is thin, manipulated, or unsafe to trade."
                ),
            },
        )

    print(f"model: {response.model}")
    print(f"usage: {response.usage}")
    for key, answer in response.nouls.items():
        print(f"  {key}: noul={answer.noul:.4f}")


if __name__ == "__main__":
    main()
