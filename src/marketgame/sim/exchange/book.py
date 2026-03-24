from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Deque

from marketgame.sim.models import Order


class LimitOrderBook:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._bids: dict[float, Deque[Order]] = {}
        self._asks: dict[float, Deque[Order]] = {}
        self._orders: dict[str, Order] = {}

    def add_order(self, order: Order) -> None:
        if order.symbol != self.symbol:
            raise ValueError(f"order symbol {order.symbol!r} does not match book {self.symbol!r}")

        levels = self._levels_for(order.side)
        levels.setdefault(order.price, deque()).append(order)
        self._orders[order.order_id] = order

    def best_bid(self) -> Order | None:
        return self._best_order(self._bids, reverse=True)

    def best_ask(self) -> Order | None:
        return self._best_order(self._asks, reverse=False)

    def pop_best_bid(self) -> Order | None:
        return self._pop_best(self._bids, reverse=True)

    def pop_best_ask(self) -> Order | None:
        return self._pop_best(self._asks, reverse=False)

    def cancel_order(self, order_id: str) -> Order | None:
        order = self._orders.pop(order_id, None)
        if order is None:
            return None

        levels = self._levels_for(order.side)
        queue = levels.get(order.price)
        if queue is None:
            return order

        filtered = deque(existing for existing in queue if existing.order_id != order_id)
        if filtered:
            levels[order.price] = filtered
        else:
            levels.pop(order.price, None)
        return order

    def reduce_order(self, order_id: str, qty: int) -> Order | None:
        order = self._orders.get(order_id)
        if order is None:
            return None

        remaining = order.qty - qty
        levels = self._levels_for(order.side)
        queue = levels.get(order.price)
        if queue is None:
            return None

        items = list(queue)
        index = next((i for i, existing in enumerate(items) if existing.order_id == order_id), None)
        if index is None:
            return None

        if remaining <= 0:
            items.pop(index)
            self._orders.pop(order_id, None)
            if items:
                levels[order.price] = deque(items)
            else:
                levels.pop(order.price, None)
            return None

        updated = replace(
            order,
            qty=remaining,
            status="PARTIALLY_FILLED",
        )
        items[index] = updated
        levels[order.price] = deque(items)
        self._orders[order_id] = updated
        return updated

    def has_crossed_market(self, side: str, price: float) -> bool:
        if side == "BUY":
            best_ask = self.best_ask()
            return best_ask is not None and best_ask.price <= price
        best_bid = self.best_bid()
        return best_bid is not None and best_bid.price >= price

    def _best_order(self, levels: dict[float, Deque[Order]], reverse: bool) -> Order | None:
        self._prune_empty_levels(levels)
        if not levels:
            return None

        best_price = max(levels) if reverse else min(levels)
        queue = levels[best_price]
        while queue and queue[0].order_id not in self._orders:
            queue.popleft()
        if not queue:
            levels.pop(best_price, None)
            return self._best_order(levels, reverse)
        return queue[0]

    def _pop_best(self, levels: dict[float, Deque[Order]], reverse: bool) -> Order | None:
        best = self._best_order(levels, reverse)
        if best is None:
            return None

        queue = levels[best.price]
        popped = queue.popleft()
        self._orders.pop(popped.order_id, None)
        if not queue:
            levels.pop(best.price, None)
        return popped

    def _levels_for(self, side: str) -> dict[float, Deque[Order]]:
        return self._bids if side == "BUY" else self._asks

    @staticmethod
    def _prune_empty_levels(levels: dict[float, Deque[Order]]) -> None:
        empty_prices = [price for price, queue in levels.items() if not queue]
        for price in empty_prices:
            levels.pop(price, None)
