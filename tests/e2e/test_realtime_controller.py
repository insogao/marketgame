from marketgame.realtime import RealtimeSimulationController


def test_realtime_controller_start_pause_resume_and_reset() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=20,
        base_delay_seconds=0.0,
    )

    assert controller.snapshot()["status"] == "idle"

    controller.start()
    first_batch = controller.advance_one()

    assert controller.snapshot()["status"] == "running"
    assert controller.snapshot()["processed_events"] == 1
    assert first_batch

    controller.pause()
    paused_count = controller.snapshot()["processed_events"]

    assert controller.advance_one() == []
    assert controller.snapshot()["status"] == "paused"
    assert controller.snapshot()["processed_events"] == paused_count

    controller.resume()
    controller.advance_one()

    assert controller.snapshot()["status"] == "running"
    assert controller.snapshot()["processed_events"] > paused_count

    controller.reset()
    reset_state = controller.snapshot()

    assert reset_state["status"] == "idle"
    assert reset_state["processed_events"] == 0
    assert reset_state["bars"] == []


def test_realtime_controller_scales_wall_clock_delay_by_speed() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=20,
        base_delay_seconds=0.2,
    )

    assert controller.wall_clock_delay_for_gap(5) == 1.0

    controller.set_speed(2.0)
    assert controller.wall_clock_delay_for_gap(5) == 0.5

    controller.set_speed(0.5)
    assert controller.wall_clock_delay_for_gap(5) == 2.0


def test_realtime_controller_snapshot_includes_recent_trades() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=80,
        base_delay_seconds=0.0,
    )
    controller.start()

    while controller.status == "running":
        controller.advance_one()
        snapshot = controller.snapshot()
        if snapshot["trades"]:
            break

    assert snapshot["trades"]
    assert snapshot["latest_trade"] is not None


def test_realtime_controller_uses_finer_default_chart_interval() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=250,
        bar_interval="10s",
        base_delay_seconds=0.0,
    )
    controller.start()

    while controller.status == "running":
        controller.advance_one()

    snapshot = controller.snapshot()

    assert snapshot["bar_interval"] == "10s"
    assert len(snapshot["bars"]) > 2


def test_realtime_controller_completes_when_duration_horizon_is_reached() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=20,
        bar_interval="10s",
        base_delay_seconds=0.0,
    )
    controller.start()

    while controller.status == "running":
        controller.advance_one()

    snapshot = controller.snapshot()

    assert snapshot["status"] == "completed"
    assert snapshot["last_event_ts"] <= 20
    assert snapshot["duration_seconds"] == 20


def test_realtime_controller_snapshot_expands_whitespace_slots_to_duration() -> None:
    controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=300,
        bar_interval="10s",
        base_delay_seconds=0.0,
    )
    controller.start()

    while controller.status == "running":
        controller.advance_one()

    snapshot = controller.snapshot()

    assert snapshot["bar_interval"] == "10s"
    assert len(snapshot["bars"]) == 30
    assert any(bar["is_whitespace"] for bar in snapshot["bars"])
