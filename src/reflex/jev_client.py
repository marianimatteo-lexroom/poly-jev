from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import Settings


class JevError(RuntimeError):
    pass


def noul(instructions: str) -> dict[str, Any]:
    """A yes/no question — Jev returns a truth probability in [0, 1]."""
    return {"type": "noul", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
    """A multiple-choice question (up to 255 options) — Jev returns the
    selected option plus a probability distribution over all options."""
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, criteria: list[str]) -> dict[str, Any]:
    """A rubric with 2-10 ordered levels — Jev returns a continuous score."""
    return {"type": "score", "instructions": instructions, "criteria": criteria}


@dataclass(frozen=True)
class Answer:
    raw: dict[str, Any]

    @property
    def noul(self) -> float:
        return float(self.raw["noul"])

    @property
    def choice(self) -> str:
        return str(self.raw["choice"])

    @property
    def score(self) -> float:
        return float(self.raw["score"])

    @property
    def probabilities(self) -> dict[str, float]:
        return self.raw.get("probabilities", {})

    @property
    def confidence(self) -> float | None:
        val = self.raw.get("confidence")
        return float(val) if val is not None else None


@dataclass(frozen=True)
class JevResponse:
    model: str
    answers: dict[str, Answer]


class JevClient:
    """Thin client for TypeSafe AI's Jev system-one model.

    Talks to the documented REST endpoint (POST /v1/systemone) directly
    rather than pinning to a specific SDK release — if you install the
    official `typesafe-sdk` / `@typesafe-ai/sdk` package, swap this class's
    `ask()` for a call into it; everything downstream (edge_engine, etc.)
    only depends on `JevResponse`/`Answer`.
    """

    def __init__(self, settings: Settings, session: requests.Session | None = None):
        if not settings.typesafe_api_key:
            raise JevError("TYPESAFE_API_KEY is not set")
        self._settings = settings
        self._session = session or requests.Session()

    def ask(self, state: Any, questions: dict[str, dict[str, Any]], *, max_retries: int = 5) -> JevResponse:
        payload = {"model": self._settings.jev_model, "state": state, "questions": questions}
        headers = {
            "Authorization": f"Bearer {self._settings.typesafe_api_key}",
            "Content-Type": "application/json",
        }

        backoff = 1.0
        last_exc: Exception | None = None
        for _ in range(max_retries):
            try:
                resp = self._session.post(
                    self._settings.typesafe_base_url, json=payload, headers=headers, timeout=10
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("retry-after", backoff))
                time.sleep(retry_after)
                backoff *= 2
                continue

            if resp.status_code >= 400:
                raise JevError(f"Jev request failed ({resp.status_code}): {resp.text[:500]}")

            data = resp.json()
            answers = {key: Answer(raw=val) for key, val in data["answers"].items()}
            return JevResponse(model=data.get("model", self._settings.jev_model), answers=answers)

        raise JevError(f"Jev request failed after {max_retries} retries") from last_exc
