from marketgame.sim.events import MarketEvent
from marketgame.sim.replay.store import ReplayStore


def test_basic_market_metrics_from_recorded_events() -> None:
    store = ReplayStore()
    store.append_event(
        "sim-1",
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            bid=99.0,
            ask=101.0,
            sequence_number=1,
        ),
    )
    store.append_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=2,
            price=100.0,
            qty=2,
            sequence_number=2,
        ),
    )
    store.append_event(
        "sim-1",
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=3,
            bid=100.0,
            ask=102.0,
            sequence_number=3,
        ),
    )
    store.append_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=4,
            price=102.0,
            qty=3,
            sequence_number=4,
        ),
    )

    metrics = store.get_market_metrics("sim-1")

    assert metrics["trade_count"] == 2
    assert metrics["volume"] == 5
    assert metrics["open"] == 100.0
    assert metrics["high"] == 102.0
    assert metrics["low"] == 100.0
    assert metrics["close"] == 102.0
    assert metrics["vwap"] == 101.2
    assert metrics["spread"] == 2.0
