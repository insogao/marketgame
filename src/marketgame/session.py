from __future__ import annotations

from marketgame.api.market import MarketAPI
from marketgame.sim.agents.runtime import AgentRuntime
from marketgame.sim.contracts import CancelOrderRequest, EventSubscription, SubmitOrderRequest
from marketgame.sim.events import MarketEvent
from marketgame.sim.exchange.engine import ExchangeEngine
from marketgame.sim.kernel import SimulationKernel
from marketgame.sim.market_data.service import InMemoryMarketDataService
from marketgame.sim.population import build_seeded_population
from marketgame.sim.replay.store import ReplayStore


def run_seeded_session(seed: int, symbol: str, steps: int) -> dict[str, object]:
    session_id = f"sim-{seed}"
    kernel = SimulationKernel(seed=seed)
    exchange = ExchangeEngine()
    replay_store = ReplayStore()
    market_data = InMemoryMarketDataService(replay_store=replay_store)
    market_api = MarketAPI(market_data_service=market_data)
    runtime = AgentRuntime()

    base_mid = 100.0 + kernel.master_rng.randint(0, 2) * 0.5
    agents, account_configs = build_seeded_population(
        seed=seed,
        symbol=symbol,
        counts={"market_maker": 1, "momentum": 1, "value": 1},
    )

    for agent in agents.values():
        if hasattr(agent, "fair_value"):
            agent.fair_value = base_mid + 1.5
        exchange.configure_account(
            agent.agent_id,
            initial_cash=account_configs[agent.agent_id]["initial_cash"],
            allow_short=True,
            short_margin_ratio=1.0,
            allow_margin=False,
        )
        runtime.register_agent(agent)
        runtime.subscribe(
            EventSubscription(
                simulation_id=session_id,
                subscriber_id=agent.agent_id,
                mode="LIVE",
                channels=("quotes", "trades"),
                event_types=("QUOTE", "TRADE_PRINT"),
                symbols=(symbol,),
                actor_scope="PUBLIC",
            )
        )

    kernel.publish(
        MarketEvent.quote(
            simulation_id=session_id,
            symbol=symbol,
            ts=0,
            bid=base_mid - 1.0,
            ask=base_mid + 1.0,
            sequence_number=1,
            event_id=f"seed-quote-{seed}",
        )
    )

    processed_events = 0
    agent_metrics = {
        agent_id: {"events_seen": 0, "intents": 0, "orders_submitted": 0}
        for agent_id in agents
    }

    while kernel.has_events() and processed_events < steps:
        event = kernel.next_event()
        if event is None:
            break

        processed_events += 1
        market_data.publish_event(event)

        for agent_id, _agent in agents.items():
            intents = runtime.on_market_event(session_id, agent_id, event)
            if not intents:
                continue
            agent_metrics[agent_id]["events_seen"] += 1
            agent_metrics[agent_id]["intents"] += len(intents)

            for intent in intents:
                if intent.kind == "HOLD":
                    continue
                if intent.kind == "PLACE_ORDER" and intent.symbol and intent.side and intent.price is not None and intent.qty is not None:
                    result, exchange_events = exchange.submit_order(
                        SubmitOrderRequest(
                            simulation_id=session_id,
                            actor_id=intent.agent_id,
                            symbol=intent.symbol,
                            side=intent.side,
                            order_type="LIMIT",
                            price=intent.price,
                            qty=intent.qty,
                            client_order_id=None,
                        )
                    )
                    if result.accepted:
                        agent_metrics[agent_id]["orders_submitted"] += 1
                    for exchange_event in exchange_events:
                        kernel.publish(exchange_event)
                elif intent.kind == "CANCEL_ORDER" and intent.order_id is not None:
                    result, exchange_events = exchange.cancel_order(
                        CancelOrderRequest(
                            simulation_id=session_id,
                            actor_id=intent.agent_id,
                            order_id=intent.order_id,
                        )
                    )
                    if result.accepted:
                        agent_metrics[agent_id]["orders_submitted"] += 1
                    for exchange_event in exchange_events:
                        kernel.publish(exchange_event)

    trades = market_api.get_trades(session_id, symbol, 0, 10**9)
    bars = market_api.get_bars(session_id, symbol, "1m", 0, 10**9)
    return {
        "seed": seed,
        "symbol": symbol,
        "events_processed": processed_events,
        "trades": trades,
        "bars": bars,
        "agent_metrics": agent_metrics,
        "agent_accounts": {
            agent_id: exchange.get_account_snapshot(session_id, agent_id)
            for agent_id in agents
        },
    }
