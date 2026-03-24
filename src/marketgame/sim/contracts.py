from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SubmitOrderRequest:
    simulation_id: str
    actor_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT"]
    price: float
    qty: int
    client_order_id: str | None


@dataclass(frozen=True, slots=True)
class CancelOrderRequest:
    simulation_id: str
    actor_id: str
    order_id: str


@dataclass(frozen=True, slots=True)
class CommandResult:
    accepted: bool
    simulation_id: str
    actor_id: str
    command_type: Literal["SUBMIT_ORDER", "CANCEL_ORDER"]
    order_id: str | None
    reason_code: str | None
    message: str | None
    ts: int


@dataclass(frozen=True, slots=True)
class EventSubscription:
    simulation_id: str
    subscriber_id: str
    mode: Literal["LIVE", "REPLAY"]
    channels: tuple[str, ...]
    event_types: tuple[str, ...]
    symbols: tuple[str, ...]
    actor_scope: Literal["PUBLIC", "PRIVATE", "ALL"]

    def __post_init__(self) -> None:
        object.__setattr__(self, "channels", tuple(self.channels))
        object.__setattr__(self, "event_types", tuple(self.event_types))
        object.__setattr__(self, "symbols", tuple(self.symbols))
