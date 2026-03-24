from __future__ import annotations

from typing import Iterable, Protocol

from marketgame.sim.events import MarketEvent
from marketgame.sim.models import Bar, Quote, Trade


class MarketDataServiceLike(Protocol):
    def get_trades(
        self, simulation_id: str, symbol: str, from_ts: int, to_ts: int
    ) -> list[Trade]: ...

    def get_bars(
        self, simulation_id: str, symbol: str, interval: str, from_ts: int, to_ts: int
    ) -> list[Bar]: ...

    def get_quote(self, simulation_id: str, symbol: str) -> Quote | None: ...

    def stream_market(
        self, simulation_id: str, symbol: str, channels: list[str]
    ) -> Iterable[MarketEvent]: ...


class MarketAPI:
    def __init__(self, market_data_service: MarketDataServiceLike) -> None:
        self._market_data_service = market_data_service

    def get_trades(
        self, simulation_id: str, symbol: str, from_ts: int, to_ts: int
    ) -> list[Trade]:
        return self._market_data_service.get_trades(simulation_id, symbol, from_ts, to_ts)

    def get_bars(
        self, simulation_id: str, symbol: str, interval: str, from_ts: int, to_ts: int
    ) -> list[Bar]:
        return self._market_data_service.get_bars(simulation_id, symbol, interval, from_ts, to_ts)

    def get_quote(self, simulation_id: str, symbol: str) -> Quote | None:
        return self._market_data_service.get_quote(simulation_id, symbol)

    def stream_market(
        self, simulation_id: str, symbol: str, channels: list[str]
    ) -> Iterable[MarketEvent]:
        return self._market_data_service.stream_market(simulation_id, symbol, channels)
