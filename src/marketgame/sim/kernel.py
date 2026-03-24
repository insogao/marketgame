from __future__ import annotations

from dataclasses import replace
import heapq
import random
from typing import Optional

from marketgame.sim.events import MarketEvent
from marketgame.sim.rng import make_deterministic_rng


class SimulationKernel:
    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._master_rng = random.Random(seed)
        self._queue: list[tuple[tuple[int, int, int], int, MarketEvent]] = []
        self._publish_counter = 0
        self._sequence_counter = 1

    def _next_sequence_number(self) -> int:
        sequence_number = self._sequence_counter
        self._sequence_counter += 1
        return sequence_number

    def publish(self, event: MarketEvent) -> MarketEvent:
        if event.sequence_number <= 0:
            event = replace(event, sequence_number=self._next_sequence_number())
        else:
            self._sequence_counter = max(self._sequence_counter, event.sequence_number + 1)

        publish_order = self._publish_counter
        self._publish_counter += 1
        heapq.heappush(self._queue, (event.sort_key, publish_order, event))
        return event

    def next_event(self) -> Optional[MarketEvent]:
        if not self._queue:
            return None
        _, _, event = heapq.heappop(self._queue)
        return event

    def has_events(self) -> bool:
        return bool(self._queue)

    def agent_rng(self, agent_identity: str) -> random.Random:
        return make_deterministic_rng(self._seed, agent_identity)

    @property
    def master_rng(self) -> random.Random:
        return self._master_rng
