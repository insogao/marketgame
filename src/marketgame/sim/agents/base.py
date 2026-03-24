from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from marketgame.sim.events import MarketEvent

AgentIntentKind = Literal["PLACE_ORDER", "CANCEL_ORDER", "HOLD"]
OrderSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class AgentIntent:
    kind: AgentIntentKind
    agent_id: str
    symbol: str | None = None
    side: OrderSide | None = None
    price: float | None = None
    qty: int | None = None
    order_id: str | None = None
    reason: str | None = None

    @classmethod
    def place_order(
        cls,
        agent_id: str,
        symbol: str,
        side: OrderSide,
        price: float,
        qty: int,
    ) -> "AgentIntent":
        return cls(
            kind="PLACE_ORDER",
            agent_id=agent_id,
            symbol=symbol,
            side=side,
            price=price,
            qty=qty,
        )

    @classmethod
    def cancel_order(cls, agent_id: str, order_id: str, symbol: str | None = None) -> "AgentIntent":
        return cls(
            kind="CANCEL_ORDER",
            agent_id=agent_id,
            symbol=symbol,
            order_id=order_id,
        )

    @classmethod
    def hold(cls, agent_id: str, symbol: str | None = None, reason: str | None = None) -> "AgentIntent":
        return cls(kind="HOLD", agent_id=agent_id, symbol=symbol, reason=reason)


class BaseAgent(Protocol):
    agent_id: str
    symbol: str

    def on_market_event(self, simulation_id: str, event: MarketEvent) -> list[AgentIntent]:
        ...
