from marketgame.sim.events import MarketEvent
from marketgame.sim.replay.store import ReplayStore


def test_replay_store_returns_events_in_recorded_order() -> None:
    store = ReplayStore()
    first = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=2,
        bid=100.0,
        ask=102.0,
        sequence_number=2,
        event_id="evt-1",
    )
    second = MarketEvent.trade_print(
        simulation_id="sim-1",
        symbol="FOO",
        ts=1,
        price=101.0,
        qty=3,
        sequence_number=1,
        event_id="evt-2",
    )

    store.append_event("sim-1", first)
    store.append_event("sim-1", second)

    recorded = list(store.replay("sim-1"))

    assert [event.event_id for event in recorded] == ["evt-1", "evt-2"]
