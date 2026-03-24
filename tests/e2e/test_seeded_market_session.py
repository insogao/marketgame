from marketgame.session import run_seeded_session


def test_seeded_session_produces_trades_bars_and_agent_metrics() -> None:
    result = run_seeded_session(seed=7, symbol="FOO", steps=50)

    assert result["trades"]
    assert result["bars"]
    assert "market_maker" in result["agent_metrics"]
