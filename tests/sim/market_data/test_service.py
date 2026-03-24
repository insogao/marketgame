from marketgame.sim.contracts import EventSubscription
from marketgame.sim.events import EventPriority, MarketEvent
from marketgame.sim.market_data.service import InMemoryMarketDataService
from marketgame.sim.replay.store import ReplayStore


def test_market_data_service_reads_trades_quotes_and_bars() -> None:
    store = ReplayStore()
    service = InMemoryMarketDataService(replay_store=store)

    service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-quotes",
            mode="LIVE",
            channels=("quotes",),
            event_types=("QUOTE",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-trades",
            mode="LIVE",
            channels=("trades",),
            event_types=("TRADE_PRINT",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )

    service.publish_event(
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            bid=100.0,
            ask=102.0,
            sequence_number=1,
        )
    )
    service.publish_event(
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=2,
            price=101.0,
            qty=3,
            sequence_number=2,
        )
    )
    service.publish_event(
        MarketEvent.quote(
            simulation_id="sim-1",
            symbol="FOO",
            ts=3,
            bid=101.0,
            ask=103.0,
            sequence_number=3,
        )
    )

    trades = service.get_trades("sim-1", "FOO", 0, 10)
    bars = service.get_bars("sim-1", "FOO", "1m", 0, 10)
    quote = service.get_quote("sim-1", "FOO")
    streamed = list(service.stream_market("sim-1", "FOO", ["quotes", "trades"]))

    assert len(trades) == 1
    assert trades[0].price == 101.0
    assert quote is not None
    assert quote.best_bid == 101.0
    assert quote.best_ask == 103.0
    assert len(bars) == 1
    assert bars[0].open == 101.0
    assert bars[0].close == 101.0
    assert [event.event_type for event in streamed] == ["QUOTE", "TRADE_PRINT", "QUOTE"]


def test_market_data_service_filters_by_mode_channel_and_scope() -> None:
    service = InMemoryMarketDataService(replay_store=ReplayStore())

    mismatched_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-mismatch",
            mode="LIVE",
            channels=("quotes",),
            event_types=("TRADE_PRINT",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    public_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-public",
            mode="LIVE",
            channels=("quotes",),
            event_types=("QUOTE",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    public_trade_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-trades",
            mode="LIVE",
            channels=("trades",),
            event_types=("TRADE_PRINT",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    replay_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-replay",
            mode="REPLAY",
            channels=("trades",),
            event_types=("TRADE_PRINT",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )
    private_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="agent-private",
            mode="LIVE",
            channels=("private",),
            event_types=("ORDER_FILLED",),
            symbols=("FOO",),
            actor_scope="PRIVATE",
        )
    )

    public_event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=1,
        bid=100.0,
        ask=102.0,
        sequence_number=1,
    )
    private_event = MarketEvent(
        event_id="evt-2",
        simulation_id="sim-1",
        event_type="ORDER_FILLED",
        ts=2,
        priority=EventPriority.PRIVATE_NOTIFICATION,
        sequence_number=2,
        payload={"symbol": "FOO", "order_id": "ord-1"},
    )
    wrong_symbol_event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="BAR",
        ts=3,
        bid=200.0,
        ask=202.0,
        sequence_number=3,
    )

    public_notifications = service.publish_event(public_event)
    private_notifications = service.publish_event(private_event)
    wrong_symbol_notifications = service.publish_event(wrong_symbol_event)

    assert mismatched_subscription_id not in public_notifications
    assert public_subscription_id in public_notifications
    assert public_trade_subscription_id not in public_notifications
    assert replay_subscription_id not in public_notifications
    assert private_subscription_id not in public_notifications
    assert private_subscription_id in private_notifications
    assert public_subscription_id not in private_notifications
    assert wrong_symbol_notifications == []


def test_replay_subscription_receives_recorded_events_through_service_api() -> None:
    store = ReplayStore()
    service = InMemoryMarketDataService(replay_store=store)

    replay_subscription_id = service.subscribe(
        EventSubscription(
            simulation_id="sim-1",
            subscriber_id="viewer-replay",
            mode="REPLAY",
            channels=("trades",),
            event_types=("TRADE_PRINT",),
            symbols=("FOO",),
            actor_scope="PUBLIC",
        )
    )

    store.append_event(
        "sim-1",
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=1,
            price=101.0,
            qty=2,
            sequence_number=1,
            event_id="trade-1",
        ),
    )

    replay_events = list(service.stream_replay("sim-1", "FOO", ["trades"]))
    live_notifications = service.publish_event(
        MarketEvent.trade_print(
            simulation_id="sim-1",
            symbol="FOO",
            ts=2,
            price=102.0,
            qty=1,
            sequence_number=2,
            event_id="trade-2",
        )
    )

    assert replay_subscription_id not in live_notifications
    assert [event.event_id for event in replay_events] == ["trade-1"]
