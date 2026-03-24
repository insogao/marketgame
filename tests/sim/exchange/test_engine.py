from marketgame.sim.contracts import CancelOrderRequest, SubmitOrderRequest
from marketgame.sim.exchange.engine import ExchangeEngine


def submit_request(
    *,
    order_id: str | None = None,
    side: str = "BUY",
    price: float = 100.0,
    qty: int = 10,
) -> SubmitOrderRequest:
    return SubmitOrderRequest(
        simulation_id="sim-1",
        actor_id="agent-1",
        symbol="FOO",
        side=side,
        order_type="LIMIT",
        price=price,
        qty=qty,
        client_order_id=order_id,
    )


def test_valid_limit_order_is_acknowledged() -> None:
    engine = ExchangeEngine()

    result, events = engine.submit_order(submit_request())

    assert result.accepted is True
    assert result.order_id is not None
    assert any(event.event_type == "ORDER_ACKED" for event in events)
    assert any(event.event_type == "QUOTE" for event in events)


def test_crossing_orders_emit_trade_and_fill_events() -> None:
    engine = ExchangeEngine()
    engine.submit_order(submit_request(order_id="resting-sell", side="SELL", price=99.0))

    result, events = engine.submit_order(submit_request(order_id="aggressive-buy", side="BUY", price=101.0))

    assert result.accepted is True
    assert any(event.event_type == "TRADE_PRINT" for event in events)
    assert any(event.event_type == "ORDER_FILLED" for event in events)


def test_cancel_flow_for_open_order() -> None:
    engine = ExchangeEngine()
    submit_result, _ = engine.submit_order(submit_request(order_id="open-order", side="BUY", price=98.0))

    cancel_result, events = engine.cancel_order(
        CancelOrderRequest(
            simulation_id="sim-1",
            actor_id="agent-1",
            order_id=submit_result.order_id,
        )
    )

    assert cancel_result.accepted is True
    assert any(event.event_type == "ORDER_CANCELED" for event in events)


def test_rejected_submit_does_not_add_an_extra_clock_tick() -> None:
    engine = ExchangeEngine()

    rejected, _ = engine.submit_order(
        SubmitOrderRequest(
            simulation_id="sim-1",
            actor_id="agent-1",
            symbol="FOO",
            side="BUY",
            order_type="LIMIT",
            price=0.0,
            qty=10,
            client_order_id=None,
        )
    )
    accepted, _ = engine.submit_order(submit_request())

    assert rejected.ts == 1
    assert accepted.ts == 2
