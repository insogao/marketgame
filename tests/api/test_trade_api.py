from marketgame.api.trade import TradeAPI
from marketgame.sim.contracts import CancelOrderRequest, CommandResult, SubmitOrderRequest
from marketgame.sim.models import AgentAccount


class StubTradingGateway:
    def __init__(self) -> None:
        self.last_submit_request: SubmitOrderRequest | None = None
        self.last_cancel_request: CancelOrderRequest | None = None
        self.submit_result = CommandResult(
            accepted=True,
            simulation_id="sim-1",
            actor_id="agent-1",
            command_type="SUBMIT_ORDER",
            order_id="ord-1",
            reason_code=None,
            message=None,
            ts=1,
        )
        self.cancel_result = CommandResult(
            accepted=True,
            simulation_id="sim-1",
            actor_id="agent-1",
            command_type="CANCEL_ORDER",
            order_id="ord-1",
            reason_code=None,
            message=None,
            ts=2,
        )

    def submit_order(self, request: SubmitOrderRequest) -> CommandResult:
        self.last_submit_request = request
        return self.submit_result

    def cancel_order(self, request: CancelOrderRequest) -> CommandResult:
        self.last_cancel_request = request
        return self.cancel_result

    def get_positions(self, simulation_id: str, actor_id: str) -> AgentAccount:
        return AgentAccount(actor_id=actor_id, cash=123.45)

    def get_cash(self, simulation_id: str, actor_id: str) -> float:
        return 123.45

    def get_open_orders(self, simulation_id: str, actor_id: str) -> list[object]:
        return ["ord-1"]


def test_trade_api_delegates_order_and_account_calls() -> None:
    gateway = StubTradingGateway()
    api = TradeAPI(trading_gateway=gateway)
    submit_request = SubmitOrderRequest(
        simulation_id="sim-1",
        actor_id="agent-1",
        symbol="FOO",
        side="BUY",
        order_type="LIMIT",
        price=101.0,
        qty=3,
        client_order_id=None,
    )
    cancel_request = CancelOrderRequest(
        simulation_id="sim-1",
        actor_id="agent-1",
        order_id="ord-1",
    )

    assert api.submit_order(submit_request) is gateway.submit_result
    assert api.cancel_order(cancel_request) is gateway.cancel_result
    assert api.get_positions("sim-1", "agent-1").cash == 123.45
    assert api.get_cash("sim-1", "agent-1") == 123.45
    assert api.get_open_orders("sim-1", "agent-1") == ["ord-1"]
    assert gateway.last_submit_request == submit_request
    assert gateway.last_cancel_request == cancel_request
