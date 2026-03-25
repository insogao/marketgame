from __future__ import annotations

from dataclasses import asdict

from marketgame.api.market import MarketAPI
from marketgame.sim.agents.runtime import AgentRuntime
from marketgame.sim.contracts import CancelOrderRequest, EventSubscription, SubmitOrderRequest
from marketgame.sim.events import MarketEvent
from marketgame.sim.exchange.engine import ExchangeEngine
from marketgame.sim.kernel import SimulationKernel
from marketgame.sim.market_data.service import InMemoryMarketDataService
from marketgame.sim.population import build_seeded_population
from marketgame.sim.replay.store import ReplayStore


def _serialize_event(event: MarketEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "simulation_id": event.simulation_id,
        "event_type": event.event_type,
        "ts": event.ts,
        "priority": int(event.priority),
        "sequence_number": event.sequence_number,
        "payload": dict(event.payload),
    }


class SeededSimulationRunner:
    def __init__(self, *, seed: int, symbol: str, steps: int) -> None:
        self.seed = seed
        self.symbol = symbol
        self.steps = steps
        self.session_id = f"sim-{seed}"
        self.status = "idle"
        self.speed = 1.0
        self.processed_events = 0
        self.last_event_ts = 0
        self._previous_event_ts = 0
        self._kernel = SimulationKernel(seed=seed)
        self._exchange = ExchangeEngine()
        self._replay_store = ReplayStore()
        self._market_data = InMemoryMarketDataService(replay_store=self._replay_store)
        self._market_api = MarketAPI(market_data_service=self._market_data)
        self._runtime = AgentRuntime()
        self._agents: dict[str, object] = {}
        self._agent_metrics: dict[str, dict[str, int]] = {}
        self._base_mid = 100.0 + self._kernel.master_rng.randint(0, 2) * 0.5
        self._initialise()

    def start(self) -> None:
        if self.status == "completed":
            self.reset()
        self.status = "running"

    def pause(self) -> None:
        if self.status == "running":
            self.status = "paused"

    def resume(self) -> None:
        if self.status in {"paused", "idle"}:
            self.status = "running"

    def reset(self) -> None:
        self.__init__(seed=self.seed, symbol=self.symbol, steps=self.steps)

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.speed = speed

    def wall_clock_delay_for_gap(self, gap: int) -> float:
        return max(self._base_delay_seconds() * max(gap, 0) / self.speed, 0.0)

    def advance_one(self) -> list[MarketEvent]:
        if self.status != "running":
            return []
        if self.processed_events >= self.steps:
            self.status = "completed"
            return []
        event = self._kernel.next_event()
        if event is None:
            self.status = "completed"
            return []

        self.processed_events += 1
        self._previous_event_ts = self.last_event_ts
        self.last_event_ts = event.ts
        self._market_data.publish_event(event)
        self._handle_event(event)

        if self.processed_events >= self.steps or not self._kernel.has_events():
            self.status = "completed"

        return [event]

    def snapshot(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "seed": self.seed,
            "status": self.status,
            "speed": self.speed,
            "processed_events": self.processed_events,
            "trades": self._serialize_recent_trades(),
            "latest_trade": self._serialize_optional_trade(),
            "quote": self._serialize_optional_quote(),
            "bars": [asdict(bar) for bar in self._market_api.get_bars(self.session_id, self.symbol, "1m", 0, 10**9)],
            "agent_accounts": {
                agent_id: self._exchange.get_account_snapshot(self.session_id, agent_id)
                for agent_id in self._agents
            },
            "agent_metrics": self._agent_metrics,
            "last_event_ts": self.last_event_ts,
            "last_event_gap": self.last_event_ts - self._previous_event_ts if self.processed_events > 0 else 0,
        }

    def event_snapshot(self, event: MarketEvent) -> dict[str, object]:
        return _serialize_event(event)

    @property
    def agent_metrics(self) -> dict[str, dict[str, int]]:
        return self._agent_metrics

    @property
    def market_api(self) -> MarketAPI:
        return self._market_api

    def _base_delay_seconds(self) -> float:
        return 0.05

    def _initialise(self) -> None:
        agents, account_configs = build_seeded_population(
            seed=self.seed,
            symbol=self.symbol,
            counts={"market_maker": 1, "momentum": 1, "value": 1},
        )

        for agent_id, agent in agents.items():
            if hasattr(agent, "fair_value"):
                agent.fair_value = self._base_mid + 1.5
            self._exchange.configure_account(
                agent_id,
                initial_cash=float(account_configs[agent_id]["initial_cash"]),
                allow_short=True,
                short_margin_ratio=1.0,
                allow_margin=False,
            )
            self._runtime.register_agent(agent)
            self._runtime.subscribe(
                EventSubscription(
                    simulation_id=self.session_id,
                    subscriber_id=agent_id,
                    mode="LIVE",
                    channels=("quotes", "trades"),
                    event_types=("QUOTE", "TRADE_PRINT"),
                    symbols=(self.symbol,),
                    actor_scope="PUBLIC",
                )
            )
            self._agents[agent_id] = agent
            self._agent_metrics[agent_id] = {
                "events_seen": 0,
                "intents": 0,
                "orders_submitted": 0,
            }

        self._kernel.publish(
            MarketEvent.quote(
                simulation_id=self.session_id,
                symbol=self.symbol,
                ts=0,
                bid=self._base_mid - 1.0,
                ask=self._base_mid + 1.0,
                sequence_number=1,
                event_id=f"seed-quote-{self.seed}",
            )
        )

    def _handle_event(self, event: MarketEvent) -> None:
        for agent_id, _agent in self._agents.items():
            intents = self._runtime.on_market_event(self.session_id, agent_id, event)
            if not intents:
                continue
            self._agent_metrics[agent_id]["events_seen"] += 1
            self._agent_metrics[agent_id]["intents"] += len(intents)
            for intent in intents:
                if intent.kind == "HOLD":
                    continue
                if intent.kind == "PLACE_ORDER" and intent.symbol and intent.side and intent.price is not None and intent.qty is not None:
                    result, exchange_events = self._exchange.submit_order(
                        SubmitOrderRequest(
                            simulation_id=self.session_id,
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
                        self._agent_metrics[agent_id]["orders_submitted"] += 1
                    for exchange_event in exchange_events:
                        self._kernel.publish(exchange_event)
                elif intent.kind == "CANCEL_ORDER" and intent.order_id is not None:
                    result, exchange_events = self._exchange.cancel_order(
                        CancelOrderRequest(
                            simulation_id=self.session_id,
                            actor_id=intent.agent_id,
                            order_id=intent.order_id,
                        )
                    )
                    if result.accepted:
                        self._agent_metrics[agent_id]["orders_submitted"] += 1
                    for exchange_event in exchange_events:
                        self._kernel.publish(exchange_event)

    def _serialize_optional_trade(self) -> dict[str, object] | None:
        trades = self._market_api.get_trades(self.session_id, self.symbol, 0, 10**9)
        if not trades:
            return None
        return asdict(trades[-1])

    def _serialize_recent_trades(self) -> list[dict[str, object]]:
        trades = self._market_api.get_trades(self.session_id, self.symbol, 0, 10**9)
        return [asdict(trade) for trade in trades[-24:]]

    def _serialize_optional_quote(self) -> dict[str, object] | None:
        quote = self._market_api.get_quote(self.session_id, self.symbol)
        if quote is None:
            return None
        return asdict(quote)
