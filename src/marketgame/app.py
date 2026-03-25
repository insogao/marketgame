from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from marketgame.realtime import RealtimeSimulationController


class SessionStartRequest(BaseModel):
    seed: int = Field(7, ge=0)
    symbol: str = Field("FOO", min_length=1)
    duration_seconds: int = Field(300, ge=1)
    bar_interval: str = Field("10s", min_length=1)


class SessionSpeedRequest(BaseModel):
    speed: float = Field(1.0, gt=0.0)


class ConnectionHub:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()

    def register(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unregister(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._queues.discard(queue)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for queue in list(self._queues):
            await queue.put(message)


def create_app() -> FastAPI:
    web_dir = Path(__file__).resolve().parent / "web"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await _cancel_playback_task(app.state.playback_task)

    app = FastAPI(lifespan=lifespan)
    app.state.controller = RealtimeSimulationController(
        seed=7,
        symbol="FOO",
        duration_seconds=300,
        bar_interval="10s",
    )
    app.state.hub = ConnectionHub()
    app.state.playback_task = None
    if web_dir.exists():
        app.mount("/web", StaticFiles(directory=web_dir), name="web")

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse(_dashboard_html())

    @app.get("/api/session/state")
    async def get_session_state() -> dict[str, object]:
        return app.state.controller.snapshot()

    @app.post("/api/session/start")
    async def start_session(request: SessionStartRequest) -> dict[str, object]:
        await _cancel_playback_task(app.state.playback_task)
        app.state.playback_task = None
        app.state.controller = RealtimeSimulationController(
            seed=request.seed,
            symbol=request.symbol,
            duration_seconds=request.duration_seconds,
            bar_interval=request.bar_interval,
        )
        app.state.controller.start()
        await _ensure_playback_task(app)
        snapshot = app.state.controller.snapshot()
        await app.state.hub.broadcast({"type": "snapshot", "payload": snapshot})
        return snapshot

    @app.post("/api/session/pause")
    async def pause_session() -> dict[str, object]:
        app.state.controller.pause()
        snapshot = app.state.controller.snapshot()
        await app.state.hub.broadcast({"type": "status", "payload": snapshot})
        return snapshot

    @app.post("/api/session/resume")
    async def resume_session() -> dict[str, object]:
        app.state.controller.resume()
        await _ensure_playback_task(app)
        snapshot = app.state.controller.snapshot()
        await app.state.hub.broadcast({"type": "status", "payload": snapshot})
        return snapshot

    @app.post("/api/session/reset")
    async def reset_session() -> dict[str, object]:
        await _cancel_playback_task(app.state.playback_task)
        app.state.playback_task = None
        app.state.controller.reset()
        snapshot = app.state.controller.snapshot()
        await app.state.hub.broadcast({"type": "snapshot", "payload": snapshot})
        return snapshot

    @app.post("/api/session/speed")
    async def set_speed(request: SessionSpeedRequest) -> dict[str, object]:
        app.state.controller.set_speed(request.speed)
        snapshot = app.state.controller.snapshot()
        await app.state.hub.broadcast({"type": "status", "payload": snapshot})
        return snapshot

    @app.websocket("/ws/session")
    async def session_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = app.state.hub.register()
        sender = asyncio.create_task(_websocket_sender(websocket, queue))
        try:
            await websocket.send_json({"type": "snapshot", "payload": app.state.controller.snapshot()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            app.state.hub.unregister(queue)
            sender.cancel()
            try:
                await sender
            except asyncio.CancelledError:
                pass

    return app


async def _ensure_playback_task(app: FastAPI) -> None:
    task = app.state.playback_task
    if task is not None and not task.done():
        return
    app.state.playback_task = asyncio.create_task(_playback_loop(app))


async def _cancel_playback_task(task: asyncio.Task[object] | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _playback_loop(app: FastAPI) -> None:
    controller: RealtimeSimulationController = app.state.controller
    try:
        while True:
            if controller.status == "running":
                events = controller.advance_one()
                if events:
                    for event in events:
                        await app.state.hub.broadcast(
                            {
                                "type": "event",
                                "payload": controller.event_snapshot(event),
                            }
                        )
                snapshot = controller.snapshot()
                await app.state.hub.broadcast({"type": "snapshot", "payload": snapshot})
                if controller.status == "completed":
                    await app.state.hub.broadcast({"type": "status", "payload": snapshot})
                    break
                await asyncio.sleep(
                    controller.wall_clock_delay_for_gap(max(int(snapshot["last_event_gap"]), 1))
                )
                continue
            if controller.status == "completed":
                snapshot = controller.snapshot()
                await app.state.hub.broadcast({"type": "status", "payload": snapshot})
                break
            await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        raise


async def _websocket_sender(
    websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]
) -> None:
    while True:
        message = await queue.get()
        await websocket.send_json(message)


def _dashboard_html() -> str:
    web_index = Path(__file__).resolve().parent / "web" / "index.html"
    if web_index.exists():
        return web_index.read_text(encoding="utf-8")
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Market Game</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 0; background: #0d1117; color: #e6edf3; }
      main { max-width: 960px; margin: 0 auto; padding: 40px 20px; }
      .panel { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 20px; }
    </style>
  </head>
  <body>
    <main>
      <div class="panel">
        <h1>Market Game</h1>
        <p>Realtime market viewer loading. The dashboard assets will be wired in separately.</p>
      </div>
    </main>
  </body>
</html>
"""


__all__ = ["create_app"]
