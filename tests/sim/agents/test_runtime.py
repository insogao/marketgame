from __future__ import annotations

import pytest

from marketgame.sim.agents.base import AgentIntent
from marketgame.sim.agents.runtime import AgentRuntime
from marketgame.sim.contracts import EventSubscription
from marketgame.sim.events import EventPriority, MarketEvent


class RecordingAgent:
    def __init__(self) -> None:
        self.agent_id = "agent-1"
        self.symbol = "FOO"
        self.received: list[MarketEvent] = []

    def on_market_event(self, simulation_id: str, event: MarketEvent) -> list[AgentIntent]:
        self.received.append(event)
        return [AgentIntent.hold(agent_id=self.agent_id, symbol=self.symbol)]


def test_runtime_rejects_duplicate_agent_registration() -> None:
    runtime = AgentRuntime()
    agent = RecordingAgent()

    assert runtime.register_agent(agent) == "agent-1"
    with pytest.raises(ValueError, match="already registered"):
        runtime.register_agent(agent)


def test_runtime_does_not_deliver_without_subscription() -> None:
    runtime = AgentRuntime()
    agent = RecordingAgent()
    runtime.register_agent(agent)

    public_event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=1,
        bid=100.0,
        ask=102.0,
        sequence_number=1,
    )

    intents = runtime.on_market_event("sim-1", "agent-1", public_event)

    assert agent.received == []
    assert intents == []


def test_runtime_registers_subscription_and_filters_events() -> None:
    runtime = AgentRuntime()
    agent = RecordingAgent()
    runtime.register_agent(agent)
    subscription_id = runtime.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="agent-1",
            mode="LIVE",
            channels=("quotes",),
            event_types=("QUOTE",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    private_subscription_id = runtime.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="agent-1",
            mode="LIVE",
            channels=("quotes",),
            event_types=("ORDER_FILLED",),
            symbols=("FOO",),
            actor_scope="PRIVATE",
        )
    )
    assert subscription_id == "sub-1"
    assert private_subscription_id == "sub-2"

    public_event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=1,
        bid=100.0,
        ask=102.0,
        sequence_number=1,
    )
    filtered_event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="BAR",
        ts=2,
        bid=200.0,
        ask=202.0,
        sequence_number=2,
    )
    private_event = MarketEvent(
        event_id="evt-3",
        simulation_id="sim-1",
        event_type="ORDER_FILLED",
        ts=3,
        priority=EventPriority.PRIVATE_NOTIFICATION,
        sequence_number=3,
        payload={"order_id": "ord-1", "symbol": "FOO"},
    )

    public_intents = runtime.on_market_event("sim-1", "agent-1", public_event)
    filtered_intents = runtime.on_market_event("sim-1", "agent-1", filtered_event)
    private_intents = runtime.on_market_event("sim-1", "agent-1", private_event)

    assert [event.event_type for event in agent.received] == ["QUOTE", "ORDER_FILLED"]
    assert [intent.kind for intent in public_intents] == ["HOLD"]
    assert filtered_intents == []
    assert [intent.kind for intent in private_intents] == ["HOLD"]
