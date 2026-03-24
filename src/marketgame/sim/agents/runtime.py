from __future__ import annotations

from dataclasses import dataclass, field

from marketgame.sim.agents.base import AgentIntent
from marketgame.sim.contracts import EventSubscription
from marketgame.sim.events import EventPriority, MarketEvent


_PUBLIC_CHANNEL_BY_EVENT = {
    "QUOTE": "quotes",
    "TRADE_PRINT": "trades",
}


@dataclass(slots=True)
class _RegisteredAgent:
    agent: object
    subscriptions: list[EventSubscription] = field(default_factory=list)


class AgentRuntime:
    def __init__(self) -> None:
        self._agents: dict[str, _RegisteredAgent] = {}
        self._subscription_counter = 1

    def register_agent(self, agent_spec: object) -> str:
        agent_id = getattr(agent_spec, "agent_id", None)
        if not agent_id:
            raise ValueError("agent_spec must define agent_id")
        if agent_id in self._agents:
            raise ValueError(f"agent {agent_id!r} is already registered")
        self._agents[agent_id] = _RegisteredAgent(agent=agent_spec)
        return agent_id

    def subscribe(self, subscription: EventSubscription) -> str:
        registered = self._agents.get(subscription.subscriber_id)
        if registered is None:
            raise KeyError(f"unknown agent {subscription.subscriber_id!r}")
        registered.subscriptions.append(subscription)
        subscription_id = f"sub-{self._subscription_counter}"
        self._subscription_counter += 1
        return subscription_id

    def on_market_event(
        self, simulation_id: str, agent_id: str, event: MarketEvent
    ) -> list[AgentIntent]:
        registered = self._agents.get(agent_id)
        if registered is None:
            raise KeyError(f"unknown agent {agent_id!r}")
        if not self._should_deliver(registered.subscriptions, simulation_id, event):
            return []
        handler = getattr(registered.agent, "on_market_event", None)
        if handler is None:
            raise AttributeError(f"agent {agent_id!r} does not implement on_market_event")
        return handler(simulation_id, event)

    def get_agent_state(self, simulation_id: str, agent_id: str) -> dict[str, object]:
        registered = self._agents.get(agent_id)
        if registered is None:
            raise KeyError(f"unknown agent {agent_id!r}")
        state = getattr(registered.agent, "state", None)
        if isinstance(state, dict):
            return dict(state)
        return {}

    def _should_deliver(
        self, subscriptions: list[EventSubscription], simulation_id: str, event: MarketEvent
    ) -> bool:
        if not subscriptions:
            return False

        for subscription in subscriptions:
            if subscription.simulation_id != simulation_id:
                continue
            if not self._subscription_matches_symbol(subscription, event):
                continue
            if not self._subscription_matches_event_type(subscription, event):
                continue
            if event.priority == EventPriority.PRIVATE_NOTIFICATION:
                if subscription.actor_scope in {"PRIVATE", "ALL"}:
                    return True
                continue
            if subscription.actor_scope in {"PUBLIC", "ALL"}:
                return True
        return False

    def _subscription_matches_symbol(self, subscription: EventSubscription, event: MarketEvent) -> bool:
        if not subscription.symbols:
            return True
        symbol = event.payload.get("symbol")
        return symbol in subscription.symbols

    def _subscription_matches_event_type(
        self, subscription: EventSubscription, event: MarketEvent
    ) -> bool:
        if not subscription.event_types:
            return True
        channel = _PUBLIC_CHANNEL_BY_EVENT.get(event.event_type)
        if channel is not None and channel in subscription.channels:
            return True
        return event.event_type in subscription.event_types
