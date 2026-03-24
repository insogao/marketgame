from marketgame.sim.market_data.bars import BarAggregator


def test_bar_aggregator_builds_ohlcv_from_trade_events() -> None:
    aggregator = BarAggregator(interval="1m", simulation_id="sim-1", symbol="FOO")

    aggregator.apply_trade(price=100.0, qty=3, ts=0)
    aggregator.apply_trade(price=101.0, qty=2, ts=10)

    bar = aggregator.current_bar()

    assert bar.open == 100.0
    assert bar.high == 101.0
    assert bar.low == 100.0
    assert bar.close == 101.0
    assert bar.volume == 5
    assert bar.start_ts == 0
    assert bar.end_ts == 60
