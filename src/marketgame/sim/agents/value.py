from __future__ import annotations

from dataclasses import dataclass

from marketgame.sim.agents.base import AgentIntent
from marketgame.sim.events import MarketEvent


@dataclass(slots=True)
class ValueAgent:
    agent_id: str
    symbol: str
    fair_value: float
    quantity: int = 1
    threshold: float = 0.0

    def on_market_event(self, simulation_id: str, event: MarketEvent) -> list[AgentIntent]:
        if event.simulation_id != simulation_id:
            return []
        if event.payload.get("symbol") != self.symbol:
            return []
        market_price = self._market_price(event)
        if market_price is None:
            return []

        if market_price < self.fair_value - self.threshold:
            return [
                AgentIntent.place_order(
                    agent_id=self.agent_id,
                    symbol=self.symbol,
                    side="BUY",
                    price=self._buy_price(event, market_price),
                    qty=self.quantity,
                )
            ]
        if market_price > self.fair_value + self.threshold:
            return [
                AgentIntent.place_order(
                    agent_id=self.agent_id,
                    symbol=self.symbol,
                    side="SELL",
                    price=self._sell_price(event, market_price),
                    qty=self.quantity,
                )
            ]
        return [AgentIntent.hold(agent_id=self.agent_id, symbol=self.symbol)]

    def _market_price(self, event: MarketEvent) -> float | None:
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

    def _buy_price(self, event: MarketEvent, market_price: float) -> float:
        ask = event.payload.get("ask")
        if ask is not None:
            return float(ask)
        return min(self.fair_value, market_price)

    def _sell_price(self, event: MarketEvent, market_price: float) -> float:
        bid = event.payload.get("bid")
        if bid is not None:
            return float(bid)
        return max(self.fair_value, market_price)
