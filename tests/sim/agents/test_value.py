from __future__ import annotations

from marketgame.sim.agents.value import ValueAgent
from marketgame.sim.events import MarketEvent


def test_value_agent_buys_below_fair_value_and_sells_above_it() -> None:
    agent = ValueAgent(agent_id="val-1", symbol="FOO", fair_value=100.0, quantity=4)

    buy_intents = agent.on_market_event(
        "sim-1",
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            bid=95.0,
            ask=97.0,
            sequence_number=1,
        ),
    )
    sell_intents = agent.on_market_event(
        "sim-1",
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=2,
            bid=103.0,
            ask=105.0,
            sequence_number=2,
        ),
    )

    assert buy_intents[0].kind == "PLACE_ORDER"
    assert buy_intents[0].side == "BUY"
    assert buy_intents[0].qty == 4
    assert sell_intents[0].kind == "PLACE_ORDER"
    assert sell_intents[0].side == "SELL"
    assert sell_intents[0].qty == 4
