from marketgame.sim.events import MarketEvent
from marketgame.sim.kernel import SimulationKernel


def test_kernel_orders_same_timestamp_events_by_priority_then_sequence() -> None:
    kernel = SimulationKernel(seed=7)
    kernel.publish(MarketEvent.timer("sim-1", ts=10, sequence_number=2))
    kernel.publish(MarketEvent.command("sim-1", ts=10, sequence_number=1))

    first = kernel.next_event()
    second = kernel.next_event()

    assert first is not None
    assert second is not None
    assert first.priority < second.priority
    assert first.sort_key < second.sort_key


def test_kernel_orders_same_timestamp_same_priority_by_sequence_number() -> None:
    kernel = SimulationKernel(seed=7)
    kernel.publish(MarketEvent.timer("sim-1", ts=10, sequence_number=2))
    kernel.publish(MarketEvent.timer("sim-1", ts=10, sequence_number=1))

    first = kernel.next_event()
    second = kernel.next_event()

    assert first is not None
    assert second is not None
    assert first.priority == second.priority
    assert first.sequence_number < second.sequence_number
    assert first.sort_key < second.sort_key


def test_kernel_derives_stable_agent_rng_streams() -> None:
    kernel = SimulationKernel(seed=11)

    first = kernel.agent_rng("agent-a").random()
    second = kernel.agent_rng("agent-a").random()

    assert first == second
