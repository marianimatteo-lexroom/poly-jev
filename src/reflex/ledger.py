from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .executor import OrderRequest


@dataclass(frozen=True)
class Fill:
    condition_id: str
    question: str
    side: str
    price: float
    size_usd: float
    mode: str
    timestamp: float
    raw_response: dict[str, Any] | None = None

    @classmethod
    def simulated(cls, order: "OrderRequest") -> "Fill":
        return cls(
            condition_id=order.condition_id,
            question=order.question,
            side=order.side,
            price=order.price,
            size_usd=order.size_usd,
            mode="paper",
            timestamp=time.time(),
        )

    @classmethod
    def live(cls, order: "OrderRequest", response: dict[str, Any]) -> "Fill":
        return cls(
            condition_id=order.condition_id,
            question=order.question,
            side=order.side,
            price=order.price,
            size_usd=order.size_usd,
            mode="live",
            timestamp=time.time(),
            raw_response=response,
        )


class Ledger:
    """Append-only JSONL trade log. Also the source of truth for exposure
    and open-position caps in `risk_manager`."""

    def __init__(self, path: str):
        self._path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def record(self, fill: Fill) -> None:
        with open(self._path, "a") as f:
            f.write(json.dumps(asdict(fill)) + "\n")

    def read_all(self) -> list[Fill]:
        if not os.path.exists(self._path):
            return []
        fills = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    fills.append(Fill(**json.loads(line)))
        return fills

    def open_exposure_usd(self, condition_id: str | None = None) -> float:
        total = 0.0
        for fill in self.read_all():
            if condition_id is None or fill.condition_id == condition_id:
                total += fill.size_usd
        return total

    def open_position_count(self) -> int:
        # Counts distinct markets with any recorded fill. Does not yet
        # exclude markets that have since resolved and paid out/closed —
        # acceptable for the position-count cap, which exists to bound
        # concurrent open risk rather than track exact portfolio state.
        return len({fill.condition_id for fill in self.read_all()})
