from __future__ import annotations

from dataclasses import dataclass

from marketgame.sim.agents.base import AgentIntent
from marketgame.sim.events import MarketEvent


@dataclass(slots=True)
class MarketMakerAgent:
    agent_id: str
    symbol: str
    spread: float = 1.0
    quantity: int = 1

    def on_market_event(self, simulation_id: str, event: MarketEvent) -> list[AgentIntent]:
        if event.simulation_id != simulation_id:
            return []
        if event.payload.get("symbol") != self.symbol:
            return []
        mid = self._midpoint(event)
        if mid is None:
            return []
        half_spread = self.spread / 2.0
        return [
            AgentIntent.place_order(
                agent_id=self.agent_id,
                symbol=self.symbol,
                side="BUY",
                price=round(mid - half_spread, 10),
                qty=self.quantity,
            ),
            AgentIntent.place_order(
                agent_id=self.agent_id,
                symbol=self.symbol,
                side="SELL",
                price=round(mid + half_spread, 10),
                qty=self.quantity,
            ),
        ]

    def _midpoint(self, event: MarketEvent) -> float | None:
        if event.event_type == "QUOTE":
            bid = event.payload.get("bid")
            ask = event.payload.get("ask")
            if bid is None or ask is None:
                return None
            return (float(bid) + float(ask)) / 2.0
        if event.event_type == "TRADE_PRINT":
            price = event.payload.get("price")
            if price is None:
                return None
            return float(price)
        return None
