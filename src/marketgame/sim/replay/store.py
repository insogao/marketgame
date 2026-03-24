from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from marketgame.sim.events import MarketEvent
from marketgame.sim.replay.metrics import calculate_market_metrics


@dataclass(slots=True)
class _OrderLedgerEntry:
    actor_id: str
    symbol: str
    side: str
    price: float
    qty: int


@dataclass(slots=True)
class _PositionState:
    qty: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0
    last_price: float | None = None

    def apply_buy(self, price: float, qty: int) -> None:
        if qty <= 0:
            return
        self.last_price = price
        if self.qty >= 0:
            total_qty = self.qty + qty
            if total_qty > 0:
                self.avg_cost = ((self.avg_cost * self.qty) + (price * qty)) / total_qty
            else:
                self.avg_cost = 0.0
            self.qty = total_qty
            return

        cover_qty = min(qty, -self.qty)
        self.realized_pnl += (self.avg_cost - price) * cover_qty
        self.qty += cover_qty
        remaining_qty = qty - cover_qty
        if self.qty == 0:
            self.avg_cost = 0.0
        if remaining_qty > 0:
            self.qty = remaining_qty
            self.avg_cost = price

    def apply_sell(self, price: float, qty: int) -> None:
        if qty <= 0:
            return
        self.last_price = price
        if self.qty <= 0:
            total_qty = (-self.qty) + qty
            if total_qty > 0:
                self.avg_cost = ((self.avg_cost * (-self.qty)) + (price * qty)) / total_qty
            else:
                self.avg_cost = 0.0
            self.qty = -total_qty
            return

        close_qty = min(qty, self.qty)
        self.realized_pnl += (price - self.avg_cost) * close_qty
        self.qty -= close_qty
        remaining_qty = qty - close_qty
        if self.qty == 0:
            self.avg_cost = 0.0
        if remaining_qty > 0:
            self.qty = -remaining_qty
            self.avg_cost = price

    def unrealized_pnl(self, last_price: float | None) -> float:
        if last_price is None or self.qty == 0:
            return 0.0
        if self.qty > 0:
            return (last_price - self.avg_cost) * self.qty
        return (self.avg_cost - last_price) * abs(self.qty)


class ReplayStore:
    def __init__(self) -> None:
        self._events: dict[str, list[MarketEvent]] = defaultdict(list)

    def append_event(self, simulation_id: str, event: MarketEvent) -> None:
        self._events[simulation_id].append(event)

    def replay(
        self,
        simulation_id: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> Iterable[MarketEvent]:
        for event in self._events.get(simulation_id, []):
            if from_ts is not None and event.ts < from_ts:
                continue
            if to_ts is not None and event.ts > to_ts:
                continue
            yield event

    def get_agent_pnl(self, simulation_id: str, actor_id: str) -> dict[str, object]:
        order_ledger: dict[str, _OrderLedgerEntry] = {}
        open_orders: set[str] = set()
        positions: dict[str, _PositionState] = defaultdict(_PositionState)
        cash = 0.0
        last_prices: dict[str, float] = {}

        for event in self.replay(simulation_id):
            payload = event.payload
            symbol = str(payload.get("symbol", "")) if payload.get("symbol") is not None else ""
            if event.event_type == "QUOTE":
                bid = payload.get("bid")
                ask = payload.get("ask")
                if symbol and bid is not None and ask is not None:
                    last_prices[symbol] = (float(bid) + float(ask)) / 2.0
                continue

            if event.event_type == "TRADE_PRINT":
                price = payload.get("price")
                qty = payload.get("qty")
                if symbol and price is not None:
                    last_prices[symbol] = float(price)
                if price is None or qty is None:
                    continue
                buy_order_id = payload.get("buy_order_id")
                sell_order_id = payload.get("sell_order_id")
                if buy_order_id:
                    ledger = order_ledger.get(str(buy_order_id))
                    if ledger is not None and ledger.actor_id == actor_id:
                        cash -= float(price) * int(qty)
                        positions[ledger.symbol].apply_buy(float(price), int(qty))
                        open_orders.discard(str(buy_order_id))
                if sell_order_id:
                    ledger = order_ledger.get(str(sell_order_id))
                    if ledger is not None and ledger.actor_id == actor_id:
                        cash += float(price) * int(qty)
                        positions[ledger.symbol].apply_sell(float(price), int(qty))
                        open_orders.discard(str(sell_order_id))
                continue

            if event.event_type == "ORDER_ACKED":
                order_id = payload.get("order_id")
                if order_id is None:
                    continue
                owner_id = payload.get("actor_id")
                side = payload.get("side")
                order_symbol = payload.get("symbol")
                order_price = payload.get("price")
                order_qty = payload.get("qty")
                if owner_id is not None and side is not None and order_symbol is not None and order_price is not None and order_qty is not None:
                    order_ledger[str(order_id)] = _OrderLedgerEntry(
                        actor_id=str(owner_id),
                        symbol=str(order_symbol),
                        side=str(side),
                        price=float(order_price),
                        qty=int(order_qty),
                    )
                    if str(owner_id) == actor_id:
                        open_orders.add(str(order_id))
                continue

            if event.event_type not in {"ORDER_FILLED", "ORDER_PARTIALLY_FILLED", "ORDER_CANCELED", "ORDER_REJECTED"}:
                continue

            order_id = payload.get("order_id")
            if order_id is None:
                continue
            ledger = order_ledger.get(str(order_id))
            owner_id = payload.get("actor_id") or (ledger.actor_id if ledger is not None else None)
            if owner_id != actor_id:
                continue
            fill_symbol = str(payload.get("symbol") or (ledger.symbol if ledger is not None else ""))
            fill_side = str(payload.get("side") or (ledger.side if ledger is not None else ""))
            fill_price = payload.get("price")
            fill_qty = payload.get("qty")

            if event.event_type == "ORDER_CANCELED":
                open_orders.discard(str(order_id))
                continue
            if event.event_type == "ORDER_REJECTED":
                open_orders.discard(str(order_id))
                continue
            if fill_price is None or fill_qty is None or not fill_symbol:
                continue

            price = float(fill_price)
            qty = int(fill_qty)
            last_prices[fill_symbol] = price
            if fill_side == "BUY":
                cash -= price * qty
                positions[fill_symbol].apply_buy(price, qty)
            elif fill_side == "SELL":
                cash += price * qty
                positions[fill_symbol].apply_sell(price, qty)

            if event.event_type == "ORDER_FILLED":
                open_orders.discard(str(order_id))
            elif ledger is not None and qty >= ledger.qty:
                open_orders.discard(str(order_id))

        realized_pnl = sum(state.realized_pnl for state in positions.values())
        unrealized_pnl = sum(state.unrealized_pnl(last_prices.get(symbol)) for symbol, state in positions.items())
        positions_snapshot = {symbol: state.qty for symbol, state in positions.items() if state.qty != 0}
        return {
            "simulation_id": simulation_id,
            "actor_id": actor_id,
            "cash": cash,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": realized_pnl + unrealized_pnl,
            "positions": positions_snapshot,
            "open_orders": sorted(open_orders),
        }

    def get_market_metrics(self, simulation_id: str) -> dict[str, object]:
        metrics = calculate_market_metrics(list(self.replay(simulation_id)))
        return metrics.as_dict()
