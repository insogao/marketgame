from __future__ import annotations

from marketgame.sim.agents.momentum import MomentumAgent
from marketgame.sim.events import MarketEvent


def test_momentum_agent_reacts_to_recent_trade_direction() -> None:
    agent = MomentumAgent(agent_id="mom-1", symbol="FOO", quantity=3)

    first = agent.on_market_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            price=100.0,
            qty=1,
            sequence_number=1,
        ),
    )
    second = agent.on_market_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=2,
            price=101.0,
            qty=1,
            sequence_number=2,
        ),
    )
    third = agent.on_market_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=3,
            price=99.0,
            qty=1,
            sequence_number=3,
        ),
    )

    assert first == []
    assert second[0].kind == "PLACE_ORDER"
    assert second[0].side == "BUY"
    assert second[0].qty == 3
    assert third[0].kind == "PLACE_ORDER"
    assert third[0].side == "SELL"
    assert third[0].qty == 3
