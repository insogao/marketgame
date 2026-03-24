from __future__ import annotations

from typing import Protocol

from marketgame.sim.contracts import CancelOrderRequest, CommandResult, SubmitOrderRequest
from marketgame.sim.models import AgentAccount, Order


class TradingGatewayLike(Protocol):
    def submit_order(self, request: SubmitOrderRequest) -> CommandResult: ...

    def cancel_order(self, request: CancelOrderRequest) -> CommandResult: ...

    def get_positions(self, simulation_id: str, actor_id: str) -> AgentAccount: ...

    def get_cash(self, simulation_id: str, actor_id: str) -> float: ...

    def get_open_orders(self, simulation_id: str, actor_id: str) -> list[Order]: ...


class TradeAPI:
    def __init__(self, trading_gateway: TradingGatewayLike) -> None:
        self._trading_gateway = trading_gateway

    def submit_order(self, request: SubmitOrderRequest) -> CommandResult:
        return self._trading_gateway.submit_order(request)

    def cancel_order(self, request: CancelOrderRequest) -> CommandResult:
        return self._trading_gateway.cancel_order(request)

    def get_positions(self, simulation_id: str, actor_id: str) -> AgentAccount:
        return self._trading_gateway.get_positions(simulation_id, actor_id)

    def get_cash(self, simulation_id: str, actor_id: str) -> float:
        return self._trading_gateway.get_cash(simulation_id, actor_id)

    def get_open_orders(self, simulation_id: str, actor_id: str) -> list[Order]:
        return self._trading_gateway.get_open_orders(simulation_id, actor_id)
