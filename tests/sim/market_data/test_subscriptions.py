from marketgame.sim.contracts import EventSubscription
from marketgame.sim.events import MarketEvent
from marketgame.sim.market_data.service import InMemoryMarketDataService
from marketgame.sim.replay.store import ReplayStore


def test_replay_subscription_is_not_notified_by_live_publish() -> None:
    service = InMemoryMarketDataService(replay_store=ReplayStore())

    replay_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer",
            mode="REPLAY",
            channels=("quotes",),
            event_types=("QUOTE",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )

    notifications = service.publish_event(
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            bid=100.0,
            ask=102.0,
            sequence_number=1,
        )
    )

    assert replay_subscription_id not in notifications
