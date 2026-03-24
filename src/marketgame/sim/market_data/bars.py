from __future__ import annotations

from dataclasses import dataclass, field

from marketgame.sim.models import Bar


def _interval_to_seconds(interval: str) -> int:
    if interval.endswith("m"):
        return int(interval[:-1]) * 60
    if interval.endswith("h"):
        return int(interval[:-1]) * 60 * 60
    if interval.endswith("d"):
        return int(interval[:-1]) * 60 * 60 * 24
    if interval.endswith("s"):
        return int(interval[:-1])
    return int(interval)


@dataclass(slots=True)
class BarAggregator:
    interval: str
    simulation_id: str = ""
    symbol: str = ""
    _interval_seconds: int = field(init=False)
    _current_window_start: int | None = field(default=None, init=False)
    _current_bar: Bar | None = field(default=None, init=False)
    _completed_bars: list[Bar] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._interval_seconds = _interval_to_seconds(self.interval)

    def apply_trade(
        self,
        *,
        price: float,
        qty: int,
        ts: int,
        simulation_id: str | None = None,
        symbol: str | None = None,
    ) -> Bar:
        if simulation_id is not None:
            self.simulation_id = simulation_id
        if symbol is not None:
            self.symbol = symbol

        window_start = (ts // self._interval_seconds) * self._interval_seconds
        window_end = window_start + self._interval_seconds

        if self._current_window_start is None or window_start != self._current_window_start:
            if self._current_bar is not None:
                self._completed_bars.append(self._current_bar)
            self._current_window_start = window_start
            self._current_bar = Bar(
                simulation_id=self.simulation_id,
                symbol=self.symbol,
                interval=self.interval,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=qty,
                start_ts=window_start,
                end_ts=window_end,
            )
            return self._current_bar

        assert self._current_bar is not None
        self._current_bar = Bar(
            simulation_id=self._current_bar.simulation_id,
            symbol=self._current_bar.symbol,
            interval=self._current_bar.interval,
            open=self._current_bar.open,
            high=max(self._current_bar.high, price),
            low=min(self._current_bar.low, price),
            close=price,
            volume=self._current_bar.volume + qty,
            start_ts=self._current_bar.start_ts,
            end_ts=self._current_bar.end_ts,
        )
        return self._current_bar

    def current_bar(self) -> Bar:
        if self._current_bar is None:
            raise ValueError("no trades have been applied")
        return self._current_bar

    def bars(self) -> list[Bar]:
        if self._current_bar is None:
            return list(self._completed_bars)
        return [*self._completed_bars, self._current_bar]
