import asyncio

from fastapi.testclient import TestClient

from marketgame.app import _cancel_playback_task, create_app


def test_app_serves_dashboard_and_session_state() -> None:
    client = TestClient(create_app())

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Market Game" in dashboard.text
    assert "Duration" in dashboard.text
    assert "CN" in dashboard.text
    assert "INTL" in dashboard.text
    assert "1s" in dashboard.text
    assert "5m" in dashboard.text
    assert '/web/styles.css' in dashboard.text
    assert '/web/app.js' in dashboard.text

    styles = client.get("/web/styles.css")
    assert styles.status_code == 200

    script = client.get("/web/app.js")
    assert script.status_code == 200

    state = client.get("/api/session/state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["status"] == "idle"
    assert payload["speed"] == 1.0


def test_app_control_routes_update_session_state() -> None:
    client = TestClient(create_app())

    started = client.post("/api/session/start", json={"seed": 7, "symbol": "FOO", "duration_seconds": 20})
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["duration_seconds"] == 20
    assert started.json()["bar_interval"] == "10s"

    paused = client.post("/api/session/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post("/api/session/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"

    sped_up = client.post("/api/session/speed", json={"speed": 2.0})
    assert sped_up.status_code == 200
    assert sped_up.json()["speed"] == 2.0

    reset = client.post("/api/session/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "idle"


def test_websocket_sends_initial_snapshot_message() -> None:
    client = TestClient(create_app())

    with client.websocket_connect("/ws/session") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "snapshot"
    assert message["payload"]["status"] == "idle"


def test_websocket_streams_incremental_event_objects_after_start() -> None:
    client = TestClient(create_app())

    with client.websocket_connect("/ws/session") as websocket:
        first = websocket.receive_json()
        assert first["type"] == "snapshot"

        started = client.post("/api/session/start", json={"seed": 7, "symbol": "FOO", "duration_seconds": 5})
        assert started.status_code == 200

        event_message = None
        for _ in range(6):
            message = websocket.receive_json()
            if message["type"] == "event":
                event_message = message
                break

    assert event_message is not None
    assert isinstance(event_message["payload"], dict)
    assert "event_type" in event_message["payload"]


def test_cancel_playback_task_waits_for_cleanup() -> None:
    async def scenario() -> tuple[bool, bool]:
        cleanup = asyncio.Event()

        async def worker() -> None:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                await asyncio.sleep(0)
                cleanup.set()
                raise

        task = asyncio.create_task(worker())
        await asyncio.sleep(0)
        await _cancel_playback_task(task)
        return cleanup.is_set(), task.done()

    cleanup_done, task_done = asyncio.run(scenario())
    assert cleanup_done is True
    assert task_done is True
