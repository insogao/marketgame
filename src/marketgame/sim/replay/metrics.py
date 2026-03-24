from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean, pstdev

from marketgame.sim.events import MarketEvent


@dataclass(frozen=True, slots=True)
class MarketMetrics:
    trade_count: int = 0
    volume: int = 0
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    vwap: float | None = None
    volatility: float = 0.0
    spread: float | None = None
    average_spread: float | None = None
    quote_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate_market_metrics(events: list[MarketEvent]) -> MarketMetrics:
    trade_prices: list[float] = []
    trade_qtys: list[int] = []
    spreads: list[float] = []
    for event in events:
        if event.event_type == "TRADE_PRINT":
            price = event.payload.get("price")
            qty = event.payload.get("qty")
            if price is None or qty is None:
                continue
            trade_prices.append(float(price))
            trade_qtys.append(int(qty))
        elif event.event_type == "QUOTE":
            bid = event.payload.get("bid")
            ask = event.payload.get("ask")
            if bid is None or ask is None:
                continue
            spreads.append(float(ask) - float(bid))

    if not trade_prices:
        return MarketMetrics(
            spread=spreads[-1] if spreads else None,
            average_spread=mean(spreads) if spreads else None,
            quote_count=len(spreads),
        )

    total_volume = sum(trade_qtys)
    vwap = sum(price * qty for price, qty in zip(trade_prices, trade_qtys)) / total_volume if total_volume else None
    volatility = pstdev(trade_prices) if len(trade_prices) > 1 else 0.0
    return MarketMetrics(
        trade_count=len(trade_prices),
        volume=total_volume,
        open=trade_prices[0],
        high=max(trade_prices),
        low=min(trade_prices),
        close=trade_prices[-1],
        vwap=vwap,
        volatility=volatility,
        spread=spreads[-1] if spreads else None,
        average_spread=mean(spreads) if spreads else None,
        quote_count=len(spreads),
    )
