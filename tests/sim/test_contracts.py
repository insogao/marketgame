from marketgame.sim.contracts import SubmitOrderRequest
from marketgame.sim.events import EventPriority, MarketEvent


def test_submit_order_request_has_limit_type() -> None:
    request = SubmitOrderRequest(
        simulation_id="sim-1",
        actor_id="agent-1",
        symbol="FOO",
        side="BUY",
        order_type="LIMIT",
        price=101.0,
        qty=10,
        client_order_id=None,
    )

    assert request.order_type == "LIMIT"


def test_market_event_sort_key_uses_ts_priority_and_sequence() -> None:
    event = MarketEvent.timer(
        simulation_id="sim-1",
        ts=100,
        sequence_number=3,
    )

    assert event.sort_key == (100, EventPriority.TIMER, 3)


def test_market_event_payload_is_defensively_copied() -> None:
    payload = {"symbol": "FOO", "bid": 1.0}
    event = MarketEvent.quote(
        simulation_id="sim-1",
        symbol="FOO",
        ts=100,
        bid=1.0,
        ask=2.0,
        payload=payload,
    )

    payload["bid"] = 9.0

    assert event.payload["bid"] == 1.0


def test_event_subscription_coerces_inputs_to_tuples() -> None:
    from marketgame.sim.contracts import EventSubscription

    channels = ["trades", "quotes"]
    event_types = ["TRADE_PRINT"]
    symbols = ["FOO"]

    subscription = EventSubscription(
        simulation_id="sim-1",
        subscriber_id="viewer-1",
        mode="LIVE",
        channels=channels,
        event_types=event_types,
        symbols=symbols,
        actor_scope="PUBLIC",
    )

    channels.append("bars")
    event_types.append("QUOTE")
    symbols.append("BAR")

    assert subscription.channels == ("trades", "quotes")
    assert subscription.event_types == ("TRADE_PRINT",)
    assert subscription.symbols == ("FOO",)
