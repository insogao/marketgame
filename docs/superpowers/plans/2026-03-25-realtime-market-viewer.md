# Realtime Market Viewer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web-hosted market viewer with a startup command, browser dashboard, and configurable realtime playback speed on top of the existing seeded simulation.

**Architecture:** Add a small FastAPI host and a realtime session controller that reuses the current simulation core. Serve a static single-page dashboard from the same Python package, hydrate it with an HTTP snapshot, and stream incremental updates over WebSocket while the controller advances events at a configurable rate.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, pytest, static HTML/CSS/JavaScript, TradingView Lightweight Charts via CDN.

---

## Inputs

- Spec: `docs/superpowers/specs/2026-03-25-realtime-market-viewer-design.md`
- Existing runtime: `src/marketgame/session.py`, `src/marketgame/sim/*`, `src/marketgame/api/*`
- Constraint: local single-session experience first, no human order entry yet

## File Structure Map

- Create: `src/marketgame/app.py`
- Create: `src/marketgame/realtime.py`
- Create: `src/marketgame/__main__.py`
- Create: `src/marketgame/web/index.html`
- Create: `src/marketgame/web/app.js`
- Create: `src/marketgame/web/styles.css`
- Create: `scripts/start_demo.ps1`
- Modify: `pyproject.toml`
- Test: `tests/api/test_app.py`
- Test: `tests/e2e/test_realtime_controller.py`

## Chunk 1: Realtime Controller and Launch Entry

### Task 1: Add failing controller tests for playback state

**Files:**
- Create: `tests/e2e/test_realtime_controller.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing realtime controller tests**

Cover:
- starting a seeded session creates an initial snapshot
- pause stops event advancement
- resume continues advancement
- speed updates are reflected in session state
- reset rebuilds the seeded session state

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/e2e/test_realtime_controller.py -q`
Expected: FAIL because the controller module does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- a `RealtimeSimulationController` in `src/marketgame/realtime.py`
- one background playback loop
- state transitions: `idle`, `running`, `paused`, `completed`
- simple snapshot export for UI hydration

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/e2e/test_realtime_controller.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/marketgame/realtime.py tests/e2e/test_realtime_controller.py
git commit -m "feat: add realtime simulation controller"
```

### Task 2: Add a runnable module and startup script

**Files:**
- Create: `src/marketgame/__main__.py`
- Create: `scripts/start_demo.ps1`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing startup test**

Add one test that imports `marketgame.__main__` and confirms the app factory is available.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_package_imports.py tests/e2e/test_realtime_controller.py -q`
Expected: FAIL because the module entrypoint is missing

- [ ] **Step 3: Write minimal implementation**

Implement:
- `python -m marketgame` entrypoint
- a PowerShell launcher script that starts Uvicorn on a local port

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_package_imports.py tests/e2e/test_realtime_controller.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/marketgame/__main__.py scripts/start_demo.ps1 tests
git commit -m "feat: add local launcher entrypoint"
```

## Chunk 2: Web App and Frontend Viewer

### Task 3: Add failing web app tests for index, session state, and websocket stream

**Files:**
- Create: `tests/api/test_app.py`
- Create: `src/marketgame/app.py`

- [ ] **Step 1: Write the failing FastAPI tests**

Cover:
- `GET /` returns the dashboard HTML
- `GET /api/session/state` returns a typed snapshot payload
- control routes update playback state
- `WS /ws/session` sends an initial snapshot message

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/api/test_app.py -q`
Expected: FAIL because the app module does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- FastAPI app factory
- in-memory singleton controller for the local session
- dashboard page serving
- control endpoints and one websocket stream

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_app.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/marketgame/app.py tests/api/test_app.py
git commit -m "feat: add realtime web app endpoints"
```

### Task 4: Build the static dashboard with Lightweight Charts

**Files:**
- Create: `src/marketgame/web/index.html`
- Create: `src/marketgame/web/app.js`
- Create: `src/marketgame/web/styles.css`

- [ ] **Step 1: Add a failing asset-serving assertion**

Extend `tests/api/test_app.py` to assert the served HTML references the dashboard assets and Lightweight Charts loader.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/api/test_app.py -q`
Expected: FAIL because the assets do not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- dashboard layout with playback controls
- candlestick chart backed by Lightweight Charts
- status strip for quote and latest trade
- recent trade tape and agent accounts table
- WebSocket client that applies snapshot and incremental updates

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_app.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/marketgame/web tests/api/test_app.py
git commit -m "feat: add realtime dashboard frontend"
```

## Chunk 3: End-to-End Verification

### Task 5: Verify integrated local realtime experience

**Files:**
- Modify: `tests/e2e/test_realtime_controller.py`
- Modify: `tests/api/test_app.py`

- [ ] **Step 1: Add an end-to-end smoke test**

Cover:
- start session
- receive snapshot
- set speed
- resume playback
- observe state change or streamed event

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/api/test_app.py tests/e2e/test_realtime_controller.py -q`
Expected: FAIL until the full integration is wired

- [ ] **Step 3: Write minimal implementation fixes**

Connect any missing pieces between the controller, app, and frontend-facing payloads.

- [ ] **Step 4: Run targeted tests**

Run: `python -m pytest tests/api/test_app.py tests/e2e/test_realtime_controller.py -q`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src tests scripts pyproject.toml
git commit -m "feat: add local realtime market viewer"
```

## Ready State

Plan complete and saved to `docs/superpowers/plans/2026-03-25-realtime-market-viewer.md`. This plan is intended for subagent-driven execution in the current session.
