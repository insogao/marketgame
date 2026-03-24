from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from marketgame.sim.contracts import EventSubscription
from marketgame.sim.events import EventPriority, MarketEvent
from marketgame.sim.market_data.bars import BarAggregator
from marketgame.sim.models import Bar, Quote, Trade
from marketgame.sim.replay.store import ReplayStore


_EVENT_CHANNELS = {
    "QUOTE": "quotes",
    "TRADE_PRINT": "trades",
}


@dataclass(slots=True)
class _SubscriptionRecord:
    subscription_id: str
    subscription: EventSubscription


class InMemoryMarketDataService:
    def __init__(self, replay_store: ReplayStore) -> None:
        self._replay_store = replay_store
        self._subscriptions: dict[str, _SubscriptionRecord] = {}
        self._live_events: list[MarketEvent] = []
        self._subscription_counter = 1

    def subscribe(self, subscription: EventSubscription) -> str:
        subscription_id = f"sub-{self._subscription_counter}"
        self._subscription_counter += 1
        self._subscriptions[subscription_id] = _SubscriptionRecord(
            subscription_id=subscription_id,
            subscription=subscription,
        )
        return subscription_id

    def publish_event(self, event: MarketEvent) -> list[str]:
        self._replay_store.append_event(event.simulation_id, event)
        self._live_events.append(event)
        return [
            record.subscription_id
            for record in self._subscriptions.values()
            if self._is_mode_match(record.subscription, event, "LIVE")
        ]

    def get_trades(
        self, simulation_id: str, symbol: str, from_ts: int, to_ts: int
    ) -> list[Trade]:
        trades: list[Trade] = []
        for event in self._replay_store.replay(simulation_id, from_ts, to_ts):
            if event.event_type != "TRADE_PRINT":
                continue
            if event.payload.get("symbol") != symbol:
                continue
            trade_id = event.event_id or f"trade-{event.sequence_number}"
            trades.append(
                Trade(
                    trade_id=trade_id,
                    simulation_id=event.simulation_id,
                    symbol=symbol,
                    price=float(event.payload["price"]),
                    qty=int(event.payload["qty"]),
                    buy_order_id=str(event.payload.get("buy_order_id", "")),
                    sell_order_id=str(event.payload.get("sell_order_id", "")),
                    ts=event.ts,
                )
            )
        return trades

    def get_bars(
        self, simulation_id: str, symbol: str, interval: str, from_ts: int, to_ts: int
    ) -> list[Bar]:
        aggregator = BarAggregator(interval=interval, simulation_id=simulation_id, symbol=symbol)
        for trade in self.get_trades(simulation_id, symbol, from_ts, to_ts):
            aggregator.apply_trade(
                price=trade.price,
                qty=trade.qty,
                ts=trade.ts,
                simulation_id=simulation_id,
                symbol=symbol,
            )
        return aggregator.bars()

    def get_quote(self, simulation_id: str, symbol: str) -> Quote | None:
        for event in reversed(list(self._replay_store.replay(simulation_id))):
            if event.event_type != "QUOTE":
                continue
            if event.payload.get("symbol") != symbol:
                continue
            return Quote(
                simulation_id=event.simulation_id,
                symbol=symbol,
                best_bid=_maybe_float(event.payload.get("bid")),
                best_ask=_maybe_float(event.payload.get("ask")),
                bid_size=int(event.payload.get("bid_size", 0)),
                ask_size=int(event.payload.get("ask_size", 0)),
                ts=event.ts,
            )
        return None

    def stream_market(
        self, simulation_id: str, symbol: str, channels: list[str]
    ) -> Iterable[MarketEvent]:
        allowed_channels = set(channels)
        for event in self._live_events:
            if event.simulation_id != simulation_id:
                continue
            if event.payload.get("symbol") != symbol:
                continue
            if self._channel_for_event(event) not in allowed_channels:
                continue
            if not self._has_matching_subscription(event, "LIVE"):
                continue
            yield event

    def stream_replay(
        self, simulation_id: str, symbol: str, channels: list[str]
    ) -> Iterable[MarketEvent]:
        allowed_channels = set(channels)
        for event in self._replay_store.replay(simulation_id):
            if event.payload.get("symbol") != symbol:
                continue
            if self._channel_for_event(event) not in allowed_channels:
                continue
            if not self._has_matching_subscription(event, "REPLAY"):
                continue
            yield event

    def _has_matching_subscription(self, event: MarketEvent, mode: str) -> bool:
        for record in self._subscriptions.values():
            if self._is_mode_match(record.subscription, event, mode):
                return True
        return False

    def _is_mode_match(self, subscription: EventSubscription, event: MarketEvent, mode: str) -> bool:
        if subscription.mode != mode:
            return False
        return self._matches_subscription(subscription, event)

    def _matches_subscription(self, subscription: EventSubscription, event: MarketEvent) -> bool:
        if subscription.simulation_id != event.simulation_id:
            return False
        if subscription.symbols and event.payload.get("symbol") not in subscription.symbols:
            return False
        if subscription.actor_scope == "PUBLIC" and event.priority == EventPriority.PRIVATE_NOTIFICATION:
            return False
        if subscription.actor_scope == "PRIVATE" and event.priority != EventPriority.PRIVATE_NOTIFICATION:
            return False
        channel = self._channel_for_event(event)
        if subscription.channels and channel not in subscription.channels:
            return False
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False
        return True

    @staticmethod
    def _channel_for_event(event: MarketEvent) -> str:
        return _EVENT_CHANNELS.get(event.event_type, "private")


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
