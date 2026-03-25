from __future__ import annotations

from dataclasses import replace
from itertools import count
from typing import Iterable

from marketgame.sim.accounts import AccountRules, EngineAccount, OrderReservation
from marketgame.sim.contracts import CancelOrderRequest, CommandResult, SubmitOrderRequest
from marketgame.sim.events import EventPriority, MarketEvent
from marketgame.sim.exchange.book import LimitOrderBook
from marketgame.sim.models import AgentAccount, Order, Quote, Trade


class ExchangeEngine:
    def __init__(self) -> None:
        self._books: dict[str, LimitOrderBook] = {}
        self._order_index: dict[str, tuple[str, Order]] = {}
        self._order_reservations: dict[str, OrderReservation] = {}
        self._last_trades: dict[tuple[str, str], Trade] = {}
        self._accounts: dict[str, EngineAccount] = {}
        self._order_id_counter = count(1)
        self._trade_counter = count(1)
        self._event_sequence = count(1)
        self._clock = count(1)

    def configure_account(
        self,
        actor_id: str,
        *,
        initial_cash: float,
        allow_short: bool = True,
        short_margin_ratio: float = 1.0,
        allow_margin: bool = False,
    ) -> None:
        self._accounts[actor_id] = EngineAccount(
            rules=AccountRules(
                initial_cash=initial_cash,
                allow_short=allow_short,
                short_margin_ratio=short_margin_ratio,
                allow_margin=allow_margin,
            ),
            cash=initial_cash,
        )

    def submit_order(
        self, request: SubmitOrderRequest
    ) -> tuple[CommandResult, list[MarketEvent]]:
        timestamp = next(self._clock)
        validation_error, reservation = self._validate_submit(request, timestamp)
        if validation_error is not None:
            return validation_error, [self._rejection_event(request.simulation_id, validation_error)]

        assert reservation is not None
        order_id = request.client_order_id or f"ord-{next(self._order_id_counter)}"
        order = Order(
            order_id=order_id,
            simulation_id=request.simulation_id,
            actor_id=request.actor_id,
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            qty=request.qty,
            status="ACKED",
            created_at=timestamp,
            client_order_id=request.client_order_id,
        )
        account = self._account_for(request.actor_id)
        reservation = replace(reservation, order_id=order_id)
        self._reserve_order(account, reservation)
        book = self._book_for(request.symbol)
        events = [self._ack_event(order)]

        remaining = order
        if book.has_crossed_market(order.side, order.price):
            events.extend(self._match_order(book, remaining))
            remaining = self._current_order_state(order.order_id)

        if remaining is not None and remaining.qty > 0:
            book.add_order(remaining)
            self._order_index[remaining.order_id] = (request.symbol, remaining)
            events.append(self._quote_event(request.simulation_id, request.symbol))
        else:
            self._finalize_order(order.order_id)

        result = CommandResult(
            accepted=True,
            simulation_id=request.simulation_id,
            actor_id=request.actor_id,
            command_type="SUBMIT_ORDER",
            order_id=order_id,
            reason_code=None,
            message=None,
            ts=timestamp,
        )
        return result, events

    def cancel_order(
        self, request: CancelOrderRequest
    ) -> tuple[CommandResult, list[MarketEvent]]:
        book_entry = self._order_index.get(request.order_id)
        if book_entry is None:
            result = CommandResult(
                accepted=False,
                simulation_id=request.simulation_id,
                actor_id=request.actor_id,
                command_type="CANCEL_ORDER",
                order_id=request.order_id,
                reason_code="UNKNOWN_ORDER",
                message="order not found",
                ts=next(self._clock),
            )
            return result, [self._rejection_event(request.simulation_id, result)]

        symbol, order = book_entry
        book = self._book_for(symbol)
        removed = book.cancel_order(request.order_id)
        self._order_index.pop(request.order_id, None)
        timestamp = next(self._clock)
        events: list[MarketEvent] = []
        if removed is not None:
            self._release_order_reservation(request.order_id)
            events.append(
                self._private_event(
                    "ORDER_CANCELED",
                    request.simulation_id,
                    request.order_id,
                    timestamp,
                    {
                        "symbol": symbol,
                        "qty": order.qty,
                    },
                )
            )
            events.append(self._quote_event(request.simulation_id, symbol))

        result = CommandResult(
            accepted=True,
            simulation_id=request.simulation_id,
            actor_id=request.actor_id,
            command_type="CANCEL_ORDER",
            order_id=request.order_id,
            reason_code=None,
            message=None,
            ts=timestamp,
        )
        return result, events

    def get_positions(self, simulation_id: str, actor_id: str) -> AgentAccount:
        account = self._account_for(actor_id)
        return AgentAccount(
            actor_id=actor_id,
            cash=account.cash,
            positions=account.snapshot_positions(),
            open_orders=sorted(account.open_orders),
        )

    def get_cash(self, simulation_id: str, actor_id: str) -> float:
        return self._account_for(actor_id).cash

    def get_open_orders(self, simulation_id: str, actor_id: str) -> list[Order]:
        account = self._account_for(actor_id)
        orders: list[Order] = []
        for order_id in sorted(account.open_orders):
            entry = self._order_index.get(order_id)
            if entry is not None:
                orders.append(entry[1])
        return orders

    def get_account_snapshot(self, simulation_id: str, actor_id: str) -> dict[str, object]:
        account = self._account_for(actor_id)
        return {
            "simulation_id": simulation_id,
            "actor_id": actor_id,
            "initial_cash": account.rules.initial_cash,
            "cash": account.cash,
            "allow_short": account.rules.allow_short,
            "short_margin_ratio": account.rules.short_margin_ratio,
            "allow_margin": account.rules.allow_margin,
            "positions": account.snapshot_positions(),
            "open_orders": sorted(account.open_orders),
        }

    def get_orderbook(self, simulation_id: str, symbol: str, depth: int) -> dict[str, object]:
        book = self._book_for(symbol)
        bids = self._levels(book._bids, reverse=True, depth=depth)
        asks = self._levels(book._asks, reverse=False, depth=depth)
        return {"simulation_id": simulation_id, "symbol": symbol, "bids": bids, "asks": asks}

    def get_last_trade(self, simulation_id: str, symbol: str) -> Trade | None:
        return self._last_trades.get((simulation_id, symbol))

    def _validate_submit(
        self, request: SubmitOrderRequest, timestamp: int
    ) -> tuple[CommandResult | None, OrderReservation | None]:
        if request.order_type != "LIMIT":
            return (
                self._rejected_result(request, "INVALID_ORDER_TYPE", "only LIMIT orders are supported", timestamp),
                None,
            )
        if request.qty <= 0:
            return (
                self._rejected_result(request, "INVALID_QTY", "qty must be positive", timestamp),
                None,
            )
        if request.price <= 0:
            return (
                self._rejected_result(request, "INVALID_PRICE", "price must be positive", timestamp),
                None,
            )
        if not request.symbol:
            return (
                self._rejected_result(request, "INVALID_SYMBOL", "symbol is required", timestamp),
                None,
            )
        account = self._account_for(request.actor_id)
        reservation = self._plan_reservation(account, request)
        if reservation is None:
            reason = "INSUFFICIENT_CASH" if request.side == "BUY" else "INSUFFICIENT_SHORT_COLLATERAL"
            return (
                self._rejected_result(request, reason, "account constraints rejected the order", timestamp),
                None,
            )
        return None, reservation

    def _match_order(self, book: LimitOrderBook, order: Order) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        remaining_qty = order.qty
        current_order = order

        while remaining_qty > 0:
            resting = book.best_ask() if current_order.side == "BUY" else book.best_bid()
            if resting is None:
                break

            cross = resting.price <= current_order.price if current_order.side == "BUY" else resting.price >= current_order.price
            if not cross:
                break

            trade_qty = min(remaining_qty, resting.qty)
            trade_price = resting.price
            timestamp = next(self._clock)
            events.append(
                self._trade_event(
                    current_order.simulation_id,
                    current_order.symbol,
                    timestamp,
                    trade_price,
                    trade_qty,
                    current_order.order_id,
                    resting.order_id,
                )
            )

            remaining_qty -= trade_qty
            self._apply_fill(current_order, trade_price, trade_qty)
            self._apply_fill(resting, trade_price, trade_qty)
            filled_resting = book.reduce_order(resting.order_id, trade_qty)
            if filled_resting is None:
                self._order_index.pop(resting.order_id, None)
                self._finalize_order(resting.order_id)
                events.append(
                    self._private_event(
                        "ORDER_FILLED",
                        current_order.simulation_id,
                        resting.order_id,
                        timestamp,
                        {
                            "symbol": resting.symbol,
                            "price": resting.price,
                            "qty": resting.qty,
                        },
                    )
                )
            else:
                self._order_index[filled_resting.order_id] = (filled_resting.symbol, filled_resting)
                events.append(
                    self._private_event(
                        "ORDER_PARTIALLY_FILLED",
                        current_order.simulation_id,
                        resting.order_id,
                        timestamp,
                        {
                            "symbol": filled_resting.symbol,
                            "price": filled_resting.price,
                            "qty": trade_qty,
                            "remaining_qty": filled_resting.qty,
                        },
                    )
                )

            if remaining_qty <= 0:
                events.append(
                    self._private_event(
                        "ORDER_FILLED",
                        current_order.simulation_id,
                        current_order.order_id,
                        timestamp,
                        {
                            "symbol": current_order.symbol,
                            "price": current_order.price,
                            "qty": current_order.qty,
                        },
                    )
                )
                current_order = replace(current_order, qty=0, status="FILLED")
            else:
                current_order = replace(current_order, qty=remaining_qty, status="PARTIALLY_FILLED")
                events.append(
                    self._private_event(
                        "ORDER_PARTIALLY_FILLED",
                        current_order.simulation_id,
                        current_order.order_id,
                        timestamp,
                        {
                            "symbol": current_order.symbol,
                            "price": current_order.price,
                            "qty": trade_qty,
                            "remaining_qty": remaining_qty,
                        },
                    )
                )

        if remaining_qty > 0:
            updated = replace(current_order, qty=remaining_qty, status="PARTIALLY_FILLED")
            self._order_index[updated.order_id] = (updated.symbol, updated)
        else:
            self._order_index.pop(current_order.order_id, None)
        return events

    def _current_order_state(self, order_id: str) -> Order | None:
        entry = self._order_index.get(order_id)
        if entry is None:
            return None
        return entry[1]

    def _book_for(self, symbol: str) -> LimitOrderBook:
        book = self._books.get(symbol)
        if book is None:
            book = LimitOrderBook(symbol)
            self._books[symbol] = book
        return book

    def _account_for(self, actor_id: str) -> EngineAccount:
        account = self._accounts.get(actor_id)
        if account is None:
            account = EngineAccount(
                rules=AccountRules(
                    initial_cash=float("inf"),
                    allow_short=True,
                    short_margin_ratio=1.0,
                    allow_margin=False,
                ),
                cash=float("inf"),
            )
            self._accounts[actor_id] = account
        return account

    def _plan_reservation(
        self, account: EngineAccount, request: SubmitOrderRequest
    ) -> OrderReservation | None:
        position = account.position_for(request.symbol)
        if request.side == "BUY":
            short_available = max(-position.qty, 0) - account.reserved_short_cover_qty.get(request.symbol, 0)
            short_cover_qty = min(request.qty, max(short_available, 0))
            long_open_qty = request.qty - short_cover_qty
            cover_reference_price = position.avg_price if short_cover_qty > 0 else 0.0
            reserved_budget = (request.price * long_open_qty) + (
                max(request.price - cover_reference_price, 0.0) * short_cover_qty
            )
            if reserved_budget > account.cash + 1e-9:
                return None
            return OrderReservation(
                order_id="",
                actor_id=request.actor_id,
                symbol=request.symbol,
                side=request.side,
                limit_price=request.price,
                short_margin_ratio=account.rules.short_margin_ratio,
                reserved_budget=reserved_budget,
                long_open_qty=long_open_qty,
                short_cover_qty=short_cover_qty,
                cover_reference_price=cover_reference_price,
            )

        long_available = max(position.qty, 0) - account.reserved_long_sell_qty.get(request.symbol, 0)
        long_sell_qty = min(request.qty, max(long_available, 0))
        short_open_qty = request.qty - long_sell_qty
        if short_open_qty > 0 and not account.rules.allow_short:
            return None
        reserved_budget = request.price * short_open_qty * account.rules.short_margin_ratio
        if reserved_budget > account.cash + 1e-9:
            return None
        return OrderReservation(
            order_id="",
            actor_id=request.actor_id,
            symbol=request.symbol,
            side=request.side,
            limit_price=request.price,
            short_margin_ratio=account.rules.short_margin_ratio,
            reserved_budget=reserved_budget,
            long_sell_qty=long_sell_qty,
            short_open_qty=short_open_qty,
        )

    def _reserve_order(self, account: EngineAccount, reservation: OrderReservation) -> None:
        account.cash -= reservation.reserved_budget
        account.open_orders.add(reservation.order_id)
        if reservation.long_sell_qty > 0:
            account.reserved_long_sell_qty[reservation.symbol] = (
                account.reserved_long_sell_qty.get(reservation.symbol, 0) + reservation.long_sell_qty
            )
        if reservation.short_cover_qty > 0:
            account.reserved_short_cover_qty[reservation.symbol] = (
                account.reserved_short_cover_qty.get(reservation.symbol, 0) + reservation.short_cover_qty
            )
        self._order_reservations[reservation.order_id] = reservation

    def _release_order_reservation(self, order_id: str) -> None:
        reservation = self._order_reservations.pop(order_id, None)
        if reservation is None:
            return
        account = self._account_for(reservation.actor_id)
        account.cash += reservation.remaining_reserved_budget()
        account.open_orders.discard(order_id)
        if reservation.long_sell_qty > 0:
            updated = account.reserved_long_sell_qty.get(reservation.symbol, 0) - reservation.long_sell_qty
            if updated > 0:
                account.reserved_long_sell_qty[reservation.symbol] = updated
            else:
                account.reserved_long_sell_qty.pop(reservation.symbol, None)
        if reservation.short_cover_qty > 0:
            updated = account.reserved_short_cover_qty.get(reservation.symbol, 0) - reservation.short_cover_qty
            if updated > 0:
                account.reserved_short_cover_qty[reservation.symbol] = updated
            else:
                account.reserved_short_cover_qty.pop(reservation.symbol, None)

    def _finalize_order(self, order_id: str) -> None:
        reservation = self._order_reservations.pop(order_id, None)
        if reservation is None:
            return
        account = self._account_for(reservation.actor_id)
        account.open_orders.discard(order_id)
        if reservation.long_sell_qty > 0:
            updated = account.reserved_long_sell_qty.get(reservation.symbol, 0) - reservation.long_sell_qty
            if updated > 0:
                account.reserved_long_sell_qty[reservation.symbol] = updated
            else:
                account.reserved_long_sell_qty.pop(reservation.symbol, None)
        if reservation.short_cover_qty > 0:
            updated = account.reserved_short_cover_qty.get(reservation.symbol, 0) - reservation.short_cover_qty
            if updated > 0:
                account.reserved_short_cover_qty[reservation.symbol] = updated
            else:
                account.reserved_short_cover_qty.pop(reservation.symbol, None)

    def _apply_fill(self, order: Order, trade_price: float, fill_qty: int) -> None:
        reservation = self._order_reservations.get(order.order_id)
        if reservation is None:
            return

        account = self._account_for(order.actor_id)
        position = account.position_for(order.symbol)
        if order.side == "BUY":
            cover_qty = min(fill_qty, reservation.short_cover_qty)
            if cover_qty > 0:
                cover_delta = (
                    reservation.cover_reference_price - trade_price
                    + max(reservation.limit_price - reservation.cover_reference_price, 0.0)
                ) * cover_qty
                account.cash += cover_delta
                reservation.short_cover_qty -= cover_qty
                updated = account.reserved_short_cover_qty.get(order.symbol, 0) - cover_qty
                if updated > 0:
                    account.reserved_short_cover_qty[order.symbol] = updated
                else:
                    account.reserved_short_cover_qty.pop(order.symbol, None)
                position.apply_buy(trade_price, cover_qty)

            long_open_qty = fill_qty - cover_qty
            if long_open_qty > 0:
                account.cash += (reservation.limit_price - trade_price) * long_open_qty
                reservation.long_open_qty -= long_open_qty
                position.apply_buy(trade_price, long_open_qty)
            return

        long_sell_qty = min(fill_qty, reservation.long_sell_qty)
        if long_sell_qty > 0:
            account.cash += trade_price * long_sell_qty
            reservation.long_sell_qty -= long_sell_qty
            updated = account.reserved_long_sell_qty.get(order.symbol, 0) - long_sell_qty
            if updated > 0:
                account.reserved_long_sell_qty[order.symbol] = updated
            else:
                account.reserved_long_sell_qty.pop(order.symbol, None)
            position.apply_sell(trade_price, long_sell_qty)

        short_open_qty = fill_qty - long_sell_qty
        if short_open_qty > 0:
            account.cash += (
                (reservation.limit_price * reservation.short_margin_ratio)
                - (trade_price * reservation.short_margin_ratio)
            ) * short_open_qty
            reservation.short_open_qty -= short_open_qty
            position.apply_sell(trade_price, short_open_qty)

    def _rejected_result(
        self, request: SubmitOrderRequest, reason_code: str, message: str, timestamp: int
    ) -> CommandResult:
        return CommandResult(
            accepted=False,
            simulation_id=request.simulation_id,
            actor_id=request.actor_id,
            command_type="SUBMIT_ORDER",
            order_id=None,
            reason_code=reason_code,
            message=message,
            ts=timestamp,
        )

    def _rejection_event(
        self, simulation_id: str, result: CommandResult
    ) -> MarketEvent:
        return self._private_event(
            "ORDER_REJECTED",
            simulation_id,
            result.order_id or "",
            result.ts,
            {
                "reason_code": result.reason_code,
                "message": result.message,
            },
        )

    def _ack_event(self, order: Order) -> MarketEvent:
        return self._private_event(
            "ORDER_ACKED",
            order.simulation_id,
            order.order_id,
            order.created_at,
            {
                "symbol": order.symbol,
                "side": order.side,
                "price": order.price,
                "qty": order.qty,
            },
        )

    def _trade_event(
        self,
        simulation_id: str,
        symbol: str,
        timestamp: int,
        price: float,
        qty: int,
        buy_order_id: str,
        sell_order_id: str,
    ) -> MarketEvent:
        trade_number = next(self._trade_counter)
        trade_id = f"trade-{trade_number}"
        self._last_trades[(simulation_id, symbol)] = Trade(
            trade_id=trade_id,
            simulation_id=simulation_id,
            symbol=symbol,
            price=price,
            qty=qty,
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            ts=timestamp,
        )
        return MarketEvent(
            event_id=trade_id,
            simulation_id=simulation_id,
            event_type="TRADE_PRINT",
            ts=timestamp,
            priority=EventPriority.PUBLIC_MARKET_DATA,
            sequence_number=next(self._event_sequence),
            payload={
                "symbol": symbol,
                "price": price,
                "qty": qty,
                "buy_order_id": buy_order_id,
                "sell_order_id": sell_order_id,
            },
        )

    def _private_event(
        self,
        event_type: str,
        simulation_id: str,
        order_id: str,
        timestamp: int,
        payload: dict[str, object],
    ) -> MarketEvent:
        sequence_number = next(self._event_sequence)
        return MarketEvent(
            event_id=f"evt-{sequence_number}",
            simulation_id=simulation_id,
            event_type=event_type,
            ts=timestamp,
            priority=EventPriority.PRIVATE_NOTIFICATION,
            sequence_number=sequence_number,
            payload={"order_id": order_id, **payload},
        )

    def _quote_event(self, simulation_id: str, symbol: str) -> MarketEvent:
        quote = self._quote_snapshot(simulation_id, symbol)
        return MarketEvent.quote(
            simulation_id=simulation_id,
            symbol=symbol,
            ts=quote.ts,
            bid=quote.best_bid,
            ask=quote.best_ask,
            sequence_number=next(self._event_sequence),
            event_id=f"quote-{next(self._trade_counter)}",
            payload={
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
            },
        )

    def _quote_snapshot(self, simulation_id: str, symbol: str) -> Quote:
        book = self._book_for(symbol)
        best_bid = book.best_bid()
        best_ask = book.best_ask()
        bid_size = best_bid.qty if best_bid is not None else 0
        ask_size = best_ask.qty if best_ask is not None else 0
        return Quote(
            simulation_id=simulation_id,
            symbol=symbol,
            best_bid=None if best_bid is None else best_bid.price,
            best_ask=None if best_ask is None else best_ask.price,
            bid_size=bid_size,
            ask_size=ask_size,
            ts=next(self._clock),
        )

    @staticmethod
    def _levels(levels: dict[float, Iterable[Order]], reverse: bool, depth: int) -> list[dict[str, object]]:
        prices = sorted(levels.keys(), reverse=reverse)[:depth]
        rows: list[dict[str, object]] = []
        for price in prices:
            orders = list(levels[price])
            rows.append(
                {
                    "price": price,
                    "qty": sum(order.qty for order in orders),
                    "orders": [order.order_id for order in orders],
                }
            )
        return rows
