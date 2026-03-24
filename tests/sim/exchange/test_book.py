from marketgame.sim.models import Order
from marketgame.sim.exchange.book import LimitOrderBook


def make_order(order_id: str, price: float, created_at: int) -> Order:
    return Order(
        order_id=order_id,
        simulation_id="sim-1",
        actor_id="agent-1",
        symbol="FOO",
        side="BUY",
        price=price,
        qty=10,
        status="ACKED",
        created_at=created_at,
    )


def test_book_orders_by_price_then_time() -> None:
    book = LimitOrderBook("FOO")
    lower = make_order("o-1", price=100.0, created_at=1)
    higher = make_order("o-2", price=101.0, created_at=2)
    earlier = make_order("o-3", price=100.0, created_at=3)
    later = make_order("o-4", price=100.0, created_at=4)

    book.add_order(lower)
    book.add_order(higher)
    assert book.best_bid().order_id == "o-2"

    book = LimitOrderBook("FOO")
    book.add_order(earlier)
    book.add_order(later)
    assert book.pop_best_bid().order_id == "o-3"
    assert book.pop_best_bid().order_id == "o-4"


def test_partially_filled_order_keeps_fifo_position_at_same_price() -> None:
    book = LimitOrderBook("FOO")
    older = make_order("o-1", price=100.0, created_at=1)
    newer = make_order("o-2", price=100.0, created_at=2)

    book.add_order(older)
    book.add_order(newer)

    updated = book.reduce_order("o-1", 4)

    assert updated is not None
    assert updated.qty == 6
    assert book.pop_best_bid().order_id == "o-1"
    assert book.pop_best_bid().order_id == "o-2"
