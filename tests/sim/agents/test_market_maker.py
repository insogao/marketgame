from __future__ import annotations

from marketgame.sim.agents.market_maker import MarketMakerAgent
from marketgame.sim.events import MarketEvent


def test_market_maker_emits_two_sided_orders_around_mid() -> None:
    agent = MarketMakerAgent(agent_id="mm-1", symbol="FOO", spread=2.0, quantity=5)
    event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=10,
        bid=100.0,
        ask=104.0,
        sequence_number=1,
    )

    intents = agent.on_market_event("sim-1", event)

    assert [intent.kind for intent in intents] == ["PLACE_ORDER", "PLACE_ORDER"]
    assert intents[0].side == "BUY"
    assert intents[0].price == 101.0
    assert intents[0].qty == 5
    assert intents[1].side == "SELL"
    assert intents[1].price == 103.0
    assert intents[1].qty == 5
