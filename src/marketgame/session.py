from __future__ import annotations

from marketgame.sim.live_session import SeededSimulationRunner


def run_seeded_session(seed: int, symbol: str, steps: int) -> dict[str, object]:
    runner = SeededSimulationRunner(
        seed=seed,
        symbol=symbol,
        duration_seconds=max(steps * 10, 300),
        max_events=steps,
    )
    runner.start()
    while runner.status == "running":
        runner.advance_one()
    snapshot = runner.snapshot()
    return {
        "seed": seed,
        "symbol": symbol,
        "events_processed": snapshot["processed_events"],
        "trades": runner.market_api.get_trades(runner.session_id, symbol, 0, 10**9),
        "bars": runner.market_api.get_bars(runner.session_id, symbol, "1m", 0, 10**9),
        "agent_metrics": snapshot["agent_metrics"],
        "agent_accounts": snapshot["agent_accounts"],
    }
