from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AccountRules:
    initial_cash: float
    allow_short: bool = True
    short_margin_ratio: float = 1.0
    allow_margin: bool = False


@dataclass(slots=True)
class PositionState:
    qty: int = 0
    avg_price: float = 0.0

    def apply_buy(self, price: float, qty: int) -> None:
        if qty <= 0:
            return
        if self.qty >= 0:
            total_qty = self.qty + qty
            if total_qty > 0:
                self.avg_price = ((self.avg_price * self.qty) + (price * qty)) / total_qty
            self.qty = total_qty
            return

        cover_qty = min(qty, -self.qty)
        self.qty += cover_qty
        remaining_qty = qty - cover_qty
        if self.qty == 0:
            self.avg_price = 0.0
        if remaining_qty > 0:
            self.qty = remaining_qty
            self.avg_price = price

    def apply_sell(self, price: float, qty: int) -> None:
        if qty <= 0:
            return
        if self.qty <= 0:
            total_qty = (-self.qty) + qty
            if total_qty > 0:
                self.avg_price = ((self.avg_price * (-self.qty)) + (price * qty)) / total_qty
            self.qty = -total_qty
            return

        close_qty = min(qty, self.qty)
        self.qty -= close_qty
        remaining_qty = qty - close_qty
        if self.qty == 0:
            self.avg_price = 0.0
        if remaining_qty > 0:
            self.qty = -remaining_qty
            self.avg_price = price


@dataclass(slots=True)
class OrderReservation:
    order_id: str
    actor_id: str
    symbol: str
    side: str
    limit_price: float
    short_margin_ratio: float
    reserved_budget: float = 0.0
    long_open_qty: int = 0
    short_cover_qty: int = 0
    long_sell_qty: int = 0
    short_open_qty: int = 0
    cover_reference_price: float = 0.0

    def remaining_reserved_budget(self) -> float:
        cover_extra = max(self.limit_price - self.cover_reference_price, 0.0) * self.short_cover_qty
        long_open = self.limit_price * self.long_open_qty
        short_open = self.limit_price * self.short_open_qty * self.short_margin_ratio
        return cover_extra + long_open + short_open


@dataclass(slots=True)
class EngineAccount:
    rules: AccountRules
    cash: float
    positions: dict[str, PositionState] = field(default_factory=dict)
    open_orders: set[str] = field(default_factory=set)
    reserved_long_sell_qty: dict[str, int] = field(default_factory=dict)
    reserved_short_cover_qty: dict[str, int] = field(default_factory=dict)

    def position_for(self, symbol: str) -> PositionState:
        state = self.positions.get(symbol)
        if state is None:
            state = PositionState()
            self.positions[symbol] = state
        return state

    def snapshot_positions(self) -> dict[str, int]:
        return {
            symbol: state.qty
            for symbol, state in self.positions.items()
            if state.qty != 0
        }
