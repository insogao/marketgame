from __future__ import annotations

from marketgame.sim.events import MarketEvent
from marketgame.sim.live_session import SeededSimulationRunner


class RealtimeSimulationController:
    def __init__(
        self,
        *,
        seed: int,
        symbol: str,
        duration_seconds: int,
        bar_interval: str = "10s",
        base_delay_seconds: float = 0.05,
    ) -> None:
        self._seed = seed
        self._symbol = symbol
        self._duration_seconds = duration_seconds
        self._bar_interval = bar_interval
        self._base_delay_seconds = base_delay_seconds
        self._runner = SeededSimulationRunner(
            seed=seed,
            symbol=symbol,
            duration_seconds=duration_seconds,
            bar_interval=bar_interval,
        )

    def start(self) -> None:
        self._runner.start()

    def pause(self) -> None:
        self._runner.pause()

    def resume(self) -> None:
        self._runner.resume()

    def reset(self) -> None:
        self._runner = SeededSimulationRunner(
            seed=self._seed,
            symbol=self._symbol,
            duration_seconds=self._duration_seconds,
            bar_interval=self._bar_interval,
        )

    def set_speed(self, speed: float) -> None:
        self._runner.set_speed(speed)

    def advance_one(self) -> list[object]:
        return self._runner.advance_one()

    def wall_clock_delay_for_gap(self, gap: int) -> float:
        return max(self._base_delay_seconds * max(gap, 0) / self.snapshot()["speed"], 0.0)

    def event_snapshot(self, event: MarketEvent) -> dict[str, object]:
        return self._runner.event_snapshot(event)

    def snapshot(self) -> dict[str, object]:
        snapshot = self._runner.snapshot()
        snapshot["base_delay_seconds"] = self._base_delay_seconds
        return snapshot

    @property
    def status(self) -> str:
        return str(self.snapshot()["status"])

    @property
    def last_event_ts(self) -> int:
        return int(self.snapshot()["last_event_ts"])
