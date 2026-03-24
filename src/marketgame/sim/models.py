from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OrderSide = Literal["BUY", "SELL"]
OrderStatus = Literal[
    "PENDING",
    "ACKED",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELED",
    "REJECTED",
]


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    simulation_id: str
    actor_id: str
    symbol: str
    side: OrderSide
    price: float
    qty: int
    status: OrderStatus
    created_at: int
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: str
    simulation_id: str
    symbol: str
    price: float
    qty: int
    buy_order_id: str
    sell_order_id: str
    ts: int


@dataclass(frozen=True, slots=True)
class Quote:
    simulation_id: str
    symbol: str
    best_bid: float | None
    best_ask: float | None
    bid_size: int
    ask_size: int
    ts: int


@dataclass(frozen=True, slots=True)
class Bar:
    simulation_id: str
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    start_ts: int
    end_ts: int


@dataclass(frozen=True, slots=True)
class AgentAccount:
    actor_id: str
    cash: float
    positions: dict[str, int] = field(default_factory=dict)
    open_orders: list[str] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
