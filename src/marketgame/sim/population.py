from __future__ import annotations

from random import Random

from marketgame.sim.agents.market_maker import MarketMakerAgent
from marketgame.sim.agents.momentum import MomentumAgent
from marketgame.sim.agents.value import ValueAgent


def build_seeded_population(
    *,
    seed: int,
    symbol: str,
    counts: dict[str, int] | None = None,
) -> tuple[dict[str, object], dict[str, dict[str, float | bool]]]:
    population_counts = {
        "market_maker": 1,
        "momentum": 3,
        "value": 2,
    }
    if counts is not None:
        population_counts.update(counts)

    rng = Random(seed)
    agents: dict[str, object] = {}
    account_configs: dict[str, dict[str, float | bool]] = {}

    def agent_name(base: str, index: int, total: int) -> str:
        if total == 1:
            return base
        return f"{base}_{index + 1}"

    for index in range(population_counts["market_maker"]):
        agent_id = agent_name("market_maker", index, population_counts["market_maker"])
        agents[agent_id] = MarketMakerAgent(
            agent_id=agent_id,
            symbol=symbol,
            spread=round(1.0 + rng.random(), 2),
            quantity=rng.randint(3, 8),
        )
        account_configs[agent_id] = {
            "initial_cash": float(rng.randint(180_000, 300_000)),
            "allow_short": True,
            "short_margin_ratio": 1.0,
            "allow_margin": False,
        }

    for index in range(population_counts["momentum"]):
        agent_id = agent_name("momentum", index, population_counts["momentum"])
        agents[agent_id] = MomentumAgent(
            agent_id=agent_id,
            symbol=symbol,
            quantity=rng.randint(1, 5),
        )
        account_configs[agent_id] = {
            "initial_cash": float(rng.randint(8_000, 30_000)),
            "allow_short": True,
            "short_margin_ratio": 1.0,
            "allow_margin": False,
        }

    base_value = 100.0 + rng.randint(0, 4)
    for index in range(population_counts["value"]):
        agent_id = agent_name("value", index, population_counts["value"])
        agents[agent_id] = ValueAgent(
            agent_id=agent_id,
            symbol=symbol,
            fair_value=base_value + rng.uniform(-2.0, 3.0),
            quantity=rng.randint(2, 6),
        )
        account_configs[agent_id] = {
            "initial_cash": float(rng.randint(30_000, 90_000)),
            "allow_short": True,
            "short_margin_ratio": 1.0,
            "allow_margin": False,
        }

    return agents, account_configs
