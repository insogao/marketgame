from marketgame.api.market import MarketAPI
from marketgame.sim.events import MarketEvent
from marketgame.sim.models import Bar, Quote, Trade


class StubMarketDataService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.trades = [Trade("trade-1", "sim-1", "FOO", 101.0, 3, "buy-1", "sell-1", 2)]
        self.bars = [Bar("sim-1", "FOO", "1m", 101.0, 101.0, 101.0, 101.0, 3, 0, 60)]
        self.quote = Quote("sim-1", "FOO", 100.0, 102.0, 10, 11, 3)
        self.events = [
            MarketEvent.trade_print(
                simulation_id="sim-1",
                symbol="FOO",
                ts=2,
                price=101.0,
                qty=3,
                sequence_number=1,
            )
        ]

    def get_trades(self, simulation_id: str, symbol: str, from_ts: int, to_ts: int) -> list[Trade]:
        self.calls.append(("get_trades", (simulation_id, symbol, from_ts, to_ts)))
        return self.trades

    def get_bars(
        self, simulation_id: str, symbol: str, interval: str, from_ts: int, to_ts: int
    ) -> list[Bar]:
        self.calls.append(("get_bars", (simulation_id, symbol, interval, from_ts, to_ts)))
        return self.bars

    def get_quote(self, simulation_id: str, symbol: str) -> Quote | None:
        self.calls.append(("get_quote", (simulation_id, symbol)))
        return self.quote

    def stream_market(self, simulation_id: str, symbol: str, channels: list[str]):
        self.calls.append(("stream_market", (simulation_id, symbol, tuple(channels))))
        return iter(self.events)


def test_market_api_delegates_to_market_data_service() -> None:
    service = StubMarketDataService()
    api = MarketAPI(market_data_service=service)

    assert api.get_trades("sim-1", "FOO", 0, 10) == service.trades
    assert api.get_bars("sim-1", "FOO", "1m", 0, 10) == service.bars
    assert api.get_quote("sim-1", "FOO") == service.quote
    assert list(api.stream_market("sim-1", "FOO", ["quotes"])) == service.events
