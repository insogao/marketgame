from marketgame.sim.population import build_seeded_population


def test_seeded_population_builds_multiple_agents_with_varying_cash() -> None:
    agents, accounts = build_seeded_population(
        seed=7,
        symbol="FOO",
        counts={"market_maker": 1, "momentum": 3, "value": 2},
    )

    assert len(agents) == 6
    assert len(accounts) == 6
    assert len({config["initial_cash"] for config in accounts.values()}) > 1
    assert all(config["allow_short"] is True for config in accounts.values())
    assert all(config["short_margin_ratio"] == 1.0 for config in accounts.values())


def test_seeded_population_is_stable_for_same_seed() -> None:
    first_agents, first_accounts = build_seeded_population(
        seed=11,
        symbol="FOO",
        counts={"market_maker": 1, "momentum": 2, "value": 1},
    )
    second_agents, second_accounts = build_seeded_population(
        seed=11,
        symbol="FOO",
        counts={"market_maker": 1, "momentum": 2, "value": 1},
    )

    assert list(first_agents) == list(second_agents)
    assert first_accounts == second_accounts
