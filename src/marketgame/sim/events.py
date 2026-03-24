from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType
from typing import Any, Mapping


class EventPriority(IntEnum):
    TIMER = 10
    AGENT_WAKEUP = 20
    COMMAND = 30
    EXCHANGE = 40
    PRIVATE_NOTIFICATION = 50
    PUBLIC_MARKET_DATA = 60
    PERSISTENCE = 70


@dataclass(frozen=True, slots=True)
class MarketEvent:
    event_id: str
    simulation_id: str
    event_type: str
    ts: int
    priority: EventPriority
    sequence_number: int
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @property
    def sort_key(self) -> tuple[int, EventPriority, int]:
        return (self.ts, self.priority, self.sequence_number)

    @classmethod
    def timer(
        cls,
        simulation_id: str,
        ts: int,
        sequence_number: int,
        event_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> "MarketEvent":
        return cls(
            event_id=event_id,
            simulation_id=simulation_id,
            event_type="TIMER",
            ts=ts,
            priority=EventPriority.TIMER,
            sequence_number=sequence_number,
            payload={} if payload is None else dict(payload),
        )

    @classmethod
    def command(
        cls,
        simulation_id: str,
        ts: int,
        sequence_number: int,
        event_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> "MarketEvent":
        return cls(
            event_id=event_id,
            simulation_id=simulation_id,
            event_type="COMMAND",
            ts=ts,
            priority=EventPriority.COMMAND,
            sequence_number=sequence_number,
            payload={} if payload is None else dict(payload),
        )

    @classmethod
    def quote(
        cls,
        simulation_id: str,
        symbol: str,
        ts: int,
        bid: float | None,
        ask: float | None,
        sequence_number: int = 0,
        event_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> "MarketEvent":
        event_payload = {"symbol": symbol, "bid": bid, "ask": ask}
        if payload is not None:
            event_payload.update(payload)
        return cls(
            event_id=event_id,
            simulation_id=simulation_id,
            event_type="QUOTE",
            ts=ts,
            priority=EventPriority.PUBLIC_MARKET_DATA,
            sequence_number=sequence_number,
            payload=event_payload,
        )

    @classmethod
    def trade_print(
        cls,
        simulation_id: str,
        symbol: str,
        ts: int,
        price: float,
        qty: int,
        sequence_number: int = 0,
        event_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> "MarketEvent":
        event_payload = {"symbol": symbol, "price": price, "qty": qty}
        if payload is not None:
            event_payload.update(payload)
        return cls(
            event_id=event_id,
            simulation_id=simulation_id,
            event_type="TRADE_PRINT",
            ts=ts,
            priority=EventPriority.PUBLIC_MARKET_DATA,
            sequence_number=sequence_number,
            payload=event_payload,
        )
