# Realtime Market Viewer Design

Date: 2026-03-25
Status: Approved in chat

## Goal

Add a local interactive experience layer on top of the existing event-driven market simulator so a user can:

- start the product with a simple script or command
- open a browser entry point
- watch the market evolve in wall-clock time
- control simulation playback speed
- inspect trades, quotes, bars, and agent account state while the simulation runs

The K-line view must use a mature open-source charting library instead of a custom implementation.

## Scope

### In Scope

- Local web server for one active simulation session
- Browser dashboard served by the Python app
- HTTP endpoints for session control and snapshot reads
- WebSocket stream for incremental live updates
- Playback controls: start, pause, resume, reset, speed multiplier
- Configurable playback speed that maps simulated time to wall-clock time
- Open-source candlestick chart integration using TradingView Lightweight Charts

### Out of Scope

- Multi-user auth
- Human order entry
- Persistent database
- Multi-session orchestration
- Production deployment concerns
- Frontend framework/tooling beyond what is needed for a local dashboard

## Recommended Technical Direction

Use a thin FastAPI application as the local host runtime.

Rationale:

- The project already has plain Python APIs and an in-memory simulation core.
- FastAPI provides a clean path for HTTP control endpoints and WebSocket event streaming without forcing a larger stack.
- A single-page static frontend can be served directly by the same app, keeping startup simple.

## Architecture

### 1. Realtime Session Controller

Responsibilities:

- Own one live simulation instance
- Compose kernel, exchange, runtime, market data, and replay services
- Advance the simulation in a background task
- Pace event delivery according to playback speed
- Produce snapshots for the frontend

Key rules:

- The simulation still processes one event at a time in total event order.
- Playback speed only affects when events are exposed to the user, not event ordering.
- Pause must stop wall-clock playback without mutating simulation results.

### 2. Web Application Layer

Responsibilities:

- Serve the dashboard entry page and static assets
- Expose session lifecycle and control endpoints
- Expose snapshot reads for initial hydration
- Stream events and snapshots over WebSocket

Key routes:

- `GET /` serves the dashboard
- `POST /api/session/start`
- `POST /api/session/pause`
- `POST /api/session/resume`
- `POST /api/session/reset`
- `POST /api/session/speed`
- `GET /api/session/state`
- `WS /ws/session`

### 3. Browser Dashboard

Responsibilities:

- Render K-line chart using TradingView Lightweight Charts
- Show latest trade, quote, order-book summary, and agent account table
- Provide playback controls and status
- Apply live updates incrementally from WebSocket events

Key UI sections:

- top control bar
- candlestick chart
- latest trade and best quote summary
- recent trade tape
- agent account panel

## Time and Playback Model

The simulator already uses simulated timestamps. The realtime layer adds a wall-clock pacing rule:

- `speed = 1.0` means one simulated time unit is exposed using the baseline wall-clock delay
- `speed > 1.0` compresses delays
- `speed < 1.0` stretches delays
- `pause` freezes playback between events
- `resume` continues from the current simulation position
- `reset` rebuilds the seeded session from scratch

To keep the first version stable, the controller will normalize event gaps using a configurable base delay in seconds and cap extreme sleeps so the UI remains active even when timestamps jump.

## Data Contracts

### Session State Snapshot

```python
{
    "session_id": str,
    "symbol": str,
    "seed": int,
    "status": "idle" | "running" | "paused" | "completed",
    "speed": float,
    "processed_events": int,
    "latest_trade": Trade | None,
    "quote": Quote | None,
    "bars": list[Bar],
    "agent_accounts": dict[str, dict[str, object]],
}
```

### WebSocket Messages

```python
{
    "type": "snapshot" | "event" | "status",
    "payload": dict[str, object],
}
```

Event payloads should include enough information for the UI to update without reloading the whole session.

## File Plan

- `src/marketgame/app.py`
- `src/marketgame/realtime.py`
- `src/marketgame/web/index.html`
- `src/marketgame/web/app.js`
- `src/marketgame/web/styles.css`
- `src/marketgame/__main__.py`
- `scripts/start_demo.ps1`

## Testing Strategy

- controller tests for start, pause, resume, reset, and speed updates
- HTTP route tests for control endpoints and index page serving
- WebSocket tests for snapshot and live event delivery
- end-to-end smoke test that starts a session, advances it briefly, and confirms the UI data contract

