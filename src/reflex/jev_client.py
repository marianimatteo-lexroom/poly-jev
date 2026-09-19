from __future__ import annotations

from typesafe_sdk import Choice, Noul, Score, SystemOneResponse, TypeSafeClient
from typesafe_sdk import TypeSafeError as JevError

from .config import Settings

# Re-exported so callers (edge_engine, etc.) only need to import this module.
__all__ = ["JevClient", "JevError", "Noul", "Choice", "Score", "SystemOneResponse"]


class JevClient:
    """Thin wrapper around TypeSafe AI's official `typesafe-sdk` client.

    Verified against the live API on 2026-09-19: `TypeSafeClient().system_one(...)`
    issues `POST https://api.typesafe.ai/v1/systemone` with an `Authorization:
    Bearer <key>` header and raises `TypeSafeAuthenticationError` on a bad key
    (confirmed end-to-end with a throwaway key — request construction is
    correct, only a real `TYPESAFE_API_KEY` is needed to get a real answer
    back). Get a key at https://console.typesafe.ai/keys.

    The SDK reads `TYPESAFE_API_KEY` / `TYPESAFE_BASE_URL` /
    `TYPESAFE_DEFAULT_MODEL` from the environment itself; `settings` is only
    used here to fail fast with a clear error before the first network call.
    """

    def __init__(self, settings: Settings):
        if not settings.typesafe_api_key:
            raise JevError(
                "TYPESAFE_API_KEY is not set. Create one at https://console.typesafe.ai/keys "
                "and put it in your .env."
            )
        self._client = TypeSafeClient(api_key=settings.typesafe_api_key)

    def ask(self, state, questions) -> SystemOneResponse:
        return self._client.system_one(state=state, questions=questions)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "JevClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
