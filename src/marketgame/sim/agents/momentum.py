from __future__ import annotations

from dataclasses import dataclass

from marketgame.sim.agents.base import AgentIntent
from marketgame.sim.events import MarketEvent


@dataclass(slots=True)
class MomentumAgent:
    agent_id: str
    symbol: str
    quantity: int = 1
    last_trade_price: float | None = None

    def on_market_event(self, simulation_id: str, event: MarketEvent) -> list[AgentIntent]:
        if event.simulation_id != simulation_id:
            return []
        if event.event_type != "TRADE_PRINT":
            return []
        if event.payload.get("symbol") != self.symbol:
            return []

        price = event.payload.get("price")
        if price is None:
            return []

        current_price = float(price)
        if self.last_trade_price is None:
            self.last_trade_price = current_price
            return []

        if current_price > self.last_trade_price:
            side = "BUY"
        elif current_price < self.last_trade_price:
            side = "SELL"
        else:
            self.last_trade_price = current_price
            return [AgentIntent.hold(agent_id=self.agent_id, symbol=self.symbol)]

        self.last_trade_price = current_price
        return [
            AgentIntent.place_order(
                agent_id=self.agent_id,
                symbol=self.symbol,
                side=side,
                price=current_price,
                qty=self.quantity,
            )
        ]
