# ADR-P5.2: Overlay Architecture Decision

- **Date**: 2026-08-03
- **Status**: Decided (not yet implemented)
- **Author**: Architect

---

## Context

P5 Dashboard provides a HunterPie-style control panel. The integration goal is:

1. Dashboard always runs as the control center
2. When the game starts, a **transparent overlay** appears automatically
3. The overlay is a separate OS window — click-through, always-on-top, positioned over the game
4. Dashboard and Overlay co-exist — Dashboard is NEVER transparent, Overlay ALWAYS is

At the end of P4, `OverlayUI` was a self-contained DPG window with its **own DPG context** and **own event loop**. P5 attempted multiple approaches to integrate it with the Dashboard.

---

## Constraints

| # | Constraint |
|---|-----------|
| C1 | `dearpygui==2.3` (DPG 2.x) — fixed dependency |
| C2 | Windows-only runtime (CTypes, pymem) |
| C3 | Overlay must be transparent + click-through (Win32 `WS_EX_LAYERED \| WS_EX_TRANSPARENT`) |
| C4 | Dashboard must have a normal window (non-transparent, with title bar and close button) |
| C5 | P4 modules must not be modified (`src/core/`, `src/model/`, `src/data/`) |

---

## Tried Solutions

### Solution A: Single DPG Context + `create_viewport()` multi-viewport (P5.1.2)

**Design**: Dashboard and Overlay share one DPG context. Dashboard creates the primary viewport. Overlay creates a secondary viewport via `dpg.create_viewport(title="overlay")`. `dpg.configure_viewport("overlay", show=True/False)` controls per-viewport visibility.

**Result**: ❌ Failed

**Why**: In DPG 2.x, `dpg.window()` — the widget container for the overlay's content — **renders exclusively on the primary viewport**. The secondary viewport is a blank OS window (no widget content). The overlay's text, predictions, and checkbox appear **inside the Dashboard window**, not in their own transparent overlay.

### Solution B: Overlay Independent Thread + Own DPG Context (P5.1.1)

**Design**: Overlay runs in a daemon thread with `overlay.run()` as the thread target. `run()` creates its own `dpg.create_context()` (thread-local) + `dpg.create_viewport(title="overlay")` + own event loop. Dashboard has its own DPG context and event loop on the main thread.

**Result**: ❌ Failed — Dashboard crashes on overlay thread start

**Why**: DPG 2.x uses **GLFW** as the windowing backend. GLFW is a shared C library that is **not thread-safe**. `glfwCreateWindow()` must be called from the **main thread** that owns the GLFW context. Calling `dpg.create_viewport()` (which calls `glfwCreateWindow()`) from a daemon thread causes GLFW state corruption → the main thread's `dpg.render_dearpygui_frame()` (which calls `glfwPollEvents()`) crashes. [GLFW documentation](https://www.glfw.org/docs/3.3/intro_guide.html#thread_safety) confirms this restriction.

### Solution C: OverlayService + Command Queue (P5.2)

**Design**: Same thread model as Solution B, but with a `queue.Queue` for cross-thread commands (`show`/`hide`/`stop`). All DPG calls execute on the overlay thread — zero cross-thread DPG calls. The goal was to isolate DPG usage within each thread.

**Result**: ❌ Failed — same GLFW crash as Solution B

**Why**: The improvement in command routing didn't change the fundamental violation: `dpg.create_viewport()` still executes on a non-main thread. GLFW's main-thread requirement is absolute and cannot be circumvented by queue-based communication.

---

## Decision: Dual-Process Overlay Architecture

**We will use process-level isolation to work around the DPG/GLFW single-thread requirement.**

```
Process 1: python dashboard.py               Process 2: python overlay.py
├─ DPG context (main thread)                 ├─ DPG context (main thread)
├─ Dashboard UI (primary viewport)           ├─ OverlayUI (primary viewport)
├─ GameService → pymem reads                ├─ MemoryReader → pymem reads
├─ Controller                                ├─ StateTracker → combat state
├─ TrainingPanel / LogView / Settings        ├─ Recorder → CSV recording
└─ No overlay management                     └─ OverlayUI.run() → transparent window
```

### Rationale

| Factor | Assessment |
|--------|-----------|
| **GLFW constraint** | ✅ Each process has its own GLFW instance and main thread — zero conflict |
| **DPG compatibility** | ✅ Each process has exactly one DPG context and one primary viewport |
| **Crash isolation** | ✅ Overlay crash doesn't kill Dashboard; Dashboard crash doesn't kill overlay |
| **P4 compatibility** | ✅ Overlay process = `python main.py` (P4 standalone). No P4 module changes needed |
| **State sync** | ⚠️ Recorder CSV and log file serve as natural synchronization channels |

### State Sync Strategy

| Data | Mechanism |
|------|----------|
| Recording state | `state_tracker.is_recording` — independent per process. User toggles in whichever UI they prefer |
| Combat data (CSV) | Both processes write to `data/` — Recorder instances are independent |
| Model status | Dashboard reads `models/fatalis_ai_model.pkl` file existence |
| Log events | Both write to `blackdragon.log` via `logging_config` — file-based shared log |

### Entry Points

| Command | Purpose |
|---------|---------|
| `python dashboard.py` | Control panel only (new entry, derived from launch.py minus overlay logic) |
| `python overlay.py` | Transparent overlay only (derived from main.py) |
| `python launch.py` | Launch both: `subprocess.Popen(["python", "overlay.py"])` + Dashboard |

---

## Rejected Alternatives

### Rejected: DPG Upgrade to 1.x or DPG Next

DPG 1.x (the original C++ dear imgui binding) supports multi-viewport natively. But upgrading requires:
- Complete rewrite of all DPG calls (API is entirely different)
- New dependency management (C++ compilation required on some platforms)
- Abandonment of 385 existing DPG-based tests

**Cost**: prohibitive for the current project phase.

### Rejected: Switch to PyQt/PySide

Qt supports multi-window natively. But:
- Adds 50MB+ dependency
- Requires learning a new UI framework
- Would need complete rewrite of both Dashboard and Overlay

**Cost**: prohibitive.

---

## Next Implementation Plan

### Step 1: Revert P5.2 experimental code

Restore `src/ui/overlay.py` to its P4.5 design (before P5.1.2 multi-viewport and P5.2 thread changes). This preserves the standalone transparent overlay.

Files to revert: `src/ui/overlay.py`, `src/app/controller.py`, `src/dashboard/main_window.py`, `tests/test_overlay.py`, `tests/test_app_controller.py`, `tests/test_dashboard.py`.

### Step 2: Clean Controller

Remove overlay lifecycle methods from `AppController` that are no longer relevant (the overlay is a separate process that self-manages).

### Step 3: Create `overlay.py` entry point (at project root)

A minimal standalone script:
```python
"""BlackDragon overlay — transparent in-game prediction window."""
from src.ui.overlay import OverlayUI
import pymem, pymem.process
...
```

Essentially a simplified version of `main.py` (P4 composition root).

### Step 4: Create `launch.py` dual-launch

```python
subprocess.Popen([sys.executable, "overlay.py"])
# then start Dashboard
...
```

### Step 5: Dashboard UX Updates

- Remove "启动覆盖层" / "关闭覆盖层" toggle button
- Add "启动覆盖层" button that launches `overlay.py` subprocess
- StatusBar shows overlay process status

### Step 6: Full test pass

Target: ≥510 tests pass (all P4 + Dashboard tests intact, overlay standalone unchanged)

---

## Current Status

| Metric | Value |
|--------|-------|
| **Tests** | **510** (510 collected, all pass with `MPLBACKEND=Agg`) |
| **Last commit** | `eeeaac0` — P4.6: Finalize v0.5.0 project structure |
| **Modified (uncommitted)** | `src/ui/overlay.py`, `src/app/controller.py`, `src/dashboard/main_window.py` (P5 experiments) |
| **Untracked (P5 new files)** | `launch.py`, `src/app/`, `src/bootstrap/`, `src/dashboard/`, `src/ui/fonts.py`, 7 test files |
| **P4 core status** | `src/core/`, `src/model/`, `src/data/` — **zero diff** |
| **Known issue** | P5.2 overlay thread model crashes on real machine (GLFW violation). Unit tests pass (mock DPG) but real DPG fails. |

### Files to Revert (Step 1)

| File | Revert to |
|------|----------|
| `src/ui/overlay.py` | P4.5 design (standalone `run()`, no `start`/`stop`/queue) |
| `src/app/controller.py` | Remove `start_overlay`/`stop_overlay` overlay lifecycle methods |
| `src/dashboard/main_window.py` | Remove overlay toggle button |
| Tests | Restore overlay standalone assertions |

### Files to Keep (from P5.1)

| File | Why |
|------|-----|
| `src/app/config.py` | AppConfig — used by Dashboard |
| `src/app/game_service.py` | GameService — game detection |
| `src/app/controller.py` (core logic) | attach_game, detach_game, training, status |
| `src/bootstrap/checker.py` | DependencyChecker |
| `src/dashboard/main_window.py` (core logic) | Tabs, StatusBar, LogView, Training, CSV list |
| `src/dashboard/log_view.py`, `status_bar.py`, `training_panel.py` | Sub-components |
| `src/ui/fonts.py` | Shared CJK font — used by both Dashboard and Overlay |
| `launch.py` | Will be rewritten for dual-process launch |
| All `tests/test_app_*.py`, `test_dashboard.py`, `test_bootstrap_*.py`, etc. | Keep with necessary updates |
