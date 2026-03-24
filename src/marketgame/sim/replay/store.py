from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Iterable

from marketgame.sim.events import MarketEvent
from marketgame.sim.replay.metrics import calculate_market_metrics


class ReplayStore:
    def __init__(self) -> None:
        self._events: dict[str, list[MarketEvent]] = defaultdict(list)

    def append_event(self, simulation_id: str, event: MarketEvent) -> None:
        self._events[simulation_id].append(event)

    def replay(
        self,
        simulation_id: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> Iterable[MarketEvent]:
        for event in self._events.get(simulation_id, []):
            if from_ts is not None and event.ts < from_ts:
                continue
            if to_ts is not None and event.ts > to_ts:
                continue
            yield event

    def get_agent_pnl(self, simulation_id: str, actor_id: str) -> dict[str, object]:
        # Phase 1 does not yet persist full account history, so return a stable empty snapshot.
        return {
            "simulation_id": simulation_id,
            "actor_id": actor_id,
            "cash": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "net_pnl": 0.0,
            "positions": {},
            "open_orders": [],
        }

    def get_market_metrics(self, simulation_id: str) -> dict[str, object]:
        metrics = calculate_market_metrics(list(self.replay(simulation_id)))
        return metrics.as_dict()
