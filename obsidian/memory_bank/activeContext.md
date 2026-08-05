# Active Context — BlackDragon

## Current Phase

**P5.4 Training Pipeline — v1.1.0 (581 tests, 94% coverage)**

## Current Goal

BlackDragon v1.1.0 — one-click training pipeline integrated into Dashboard. Dual-process architecture (Dashboard + Overlay) stable. Frozen EXE support includes auto-start, model lifecycle, and `--pipeline` one-click training. 581 tests, 94% coverage.

## Key Accomplishments (P5.3 → v1.0 RC)

| Area | Status | Description |
|------|:---:|------|
| **P5.3 Dual-process** | ✅ | `launch.py` → Dashboard + `overlay.py` → Overlay (independent DPG contexts per ADR-P5.2) |
| **Auto-start** | ✅ | `auto_start_overlay=True` (ADR-P5.3); overlay retry loop for game detection |
| **PyInstaller EXE** | ✅ | Two EXEs (`BlackDragon.exe` + `BlackDragonOverlay.exe`), `--onedir` COLLECT |
| **Frozen paths** | ✅ | `controller.data_dir` frozen-aware; training `cwd=<exe_dir>`; surfacing `models/` + `data/` |
| **Model lifecycle** | ✅ | Surfaced model → train → overwrite → reload → predict (closed loop) |
| **Frozen training** | ✅ | `--pipeline` flag: one-click data clean + model train (v1.1); `--train` preserved for backward compat |
| **P5.4 Pipeline** | ✅ | `launch.py --pipeline` + Dashboard button → `data_cleaner` → `train_lgbm`; unknown-action defense; frozen support |
| **RC test** | ✅ | 6/6 scenarios passed: install / dashboard / overlay / data / model / training |
| **KB v1.0** | ✅ | 50 active docs; 16 legacy archived; ADR index; build/runtime/audit docs complete |
| **Release files** | ✅ | LICENSE (MIT), CONTRIBUTING, SECURITY, updated README (581 tests, 94%) |

## Key Architecture Decisions

- **ADR-P5.2**: Dual-process architecture (replaces failed in-process Overlay experiments)
- **ADR-P5.3**: Auto-start + recording defaults; training data surfacing
- **ADR-P5.4**: Automated training pipeline integration — `--pipeline` flag, 2-step clean+train, unknown-action defense
- **PyInstaller**: Two-EXE split with shared deps; `--pipeline` / `--train` / `--overlay` flag-based frozen mode

## Dual-Track Status

| Track | Status | Description |
|-------|--------|-------------|
| **Legacy** | `ai_engine.py` (484 lines) | God Class retained as legacy reference + P3 test-compat entry; `python ai_engine.py` fallback |
| **Extracted** | `src/core/state_tracker.py` | CombatStateTracker — pure state management, 50 tests ✅ |
| **Extracted** | `src/core/memory_reader.py` | MemoryReader — all pymem reads, 27 tests ✅ |
| **Extracted** | `src/model/predictor.py` | ActionPredictor — model load + inference, 31 tests ✅ |
| **Extracted** | `src/data/recorder.py` | CombatRecorder — daemon recording thread, 34 tests ✅ |
| **Extracted** | `src/ui/overlay.py` | OverlayUI — DearPyGui overlay, 41 tests ✅ |
| **Composition** | `main.py` | P4+ composition root — recommended entry, 20 tests ✅ |

## What We Just Completed

#### P4 Step 5 — OverlayUI Extraction ✅

- **Status**: ✅ Complete
- **Deliverables**:
  - `src/ui/__init__.py` — ui package init
  - `src/ui/overlay.py` (289 lines) — **OverlayUI** class, 100% coverage
  - `tests/test_overlay.py` — **41 tests**, all passed
- **Design**: DearPyGui overlay extraction from `Ultimate_Radar_UI` (ai_engine.py L319–469)
  - __init__ only stores injected dependencies (MemoryReader + StateTracker + Predictor + action_buffer + lock) — zero DPG/ctypes
  - _compute_frame: pure logic, 0 DPG calls, 1:1 order match with original update_logic
  - _apply_display: thin DPG application layer (set_value/configure_item)
  - _setup_dpg: DPG context/font/window/viewport + Win32 ctypes transparent overlay
  - _compute_ai_display: nova warning / prediction throttle / ACTION_DB formatting
  - last_action dropped — StateTracker owns posture FSM cursor
  - run() with try/finally for guaranteed dpg.destroy_context()
- **Review**: P4 Step 5 Review **APPROVED** — 0 blockers, 1 non-blocking observation
- **Constraint**: `ai_engine.py` / all 4 existing P4 modules untouched (dual-track)
#### P4 Step 4 — Recorder Extraction ✅

- **Status**: ✅ Complete
- **Deliverables**:
  - `src/data/__init__.py` — data package init
  - `src/data/recorder.py` (201 lines) — **CombatRecorder** class, 100% coverage
  - `tests/test_recorder.py` — **34 tests**, all passed
- **Design**: Daemon thread CSV recording from `data_logger_thread` (ai_engine.py L271–316)
  - Lifecycle: `start()` / `stop()` / `run()` — daemon thread, explicit stop
  - All memory reads via **MemoryReader** (7 calls), no direct pymem
  - All state reads via **CombatStateTracker** (`is_recording`/`phase`/`is_enraged`/`posture`)
  - action_buffer producer: `append(action_id)` with `action_lock`
  - CSV format identical to original: timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id
  - 0.1s frame interval, zone=417 gating, lazy file creation, 3-tier gating
- **SF-1 fix**: `run()` try boundary moved up to cover `_should_pause()` — exception scope parity with original `data_logger_thread`
- **Review**: P4 Step 4 Review **APPROVED** (SF-1 fixed)
- **Constraint**: `ai_engine.py` / `state_tracker.py` / `memory_reader.py` untouched (dual-track)
### P4 Step 3 — Predictor Extraction ✅

- **Status**: ✅ Complete
- **Deliverables**:
  - `src/model/__init__.py` — model package init
  - `src/model/predictor.py` (201 lines) — **ActionPredictor** class, 99% coverage
  - `tests/test_predictor.py` — **31 tests**, all passed
- **Design**: Encapsulates model loading + inference pipeline
  - 1 public method: `predict(distance, angle, posture, prev_action, phase, enrage) → [(class_id, prob), ...]`
  - 4 static methods migrated from P3.3: `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs`, `select_top_k`
  - 2 module-level constants: `_POSTURE_STAND_EXCLUDE` (15 IDs), `_POSTURE_PRONE_EXCLUDE` (37 IDs)
  - Dependencies: `joblib` + `pandas` + `numpy` + lazy `src.config.actions`
  - No pymem / dearpygui / threading / StateTracker / MemoryReader
  - Model load failure → `_model = None` → `predict()` returns `[]`
  - `predict()` returns raw (class_id, prob) tuples — ACTION_DB display formatting stays in caller (UI)
- **Review**: P4 Step 3 Review APPROVED — 0 blocking issues, 2 non-blocking suggestions
- **Constraint**: `ai_engine.py` untouched; P3.3 functions untouched (dual-track)

## What We Just Completed

### P4 Step 1 — StateTracker Extraction ✅

- **Status**: ✅ Complete
- **Deliverables**:
  - `src/core/__init__.py` — core package init
  - `src/core/state_tracker.py` (156 lines) — **CombatStateTracker** class, 100% coverage
  - `tests/test_state_tracker.py` — **50 tests**, all passed
- **Design**: Pure state management class encapsulating shared_state dict semantics
  - 7 public methods: `calc_distance_2d`, `calc_relative_angle`, `map_action` (static),
    `update_phase`, `update_enrage`, `update_posture`, `update_nova`, `reset_for_zone_change`
  - Zero external dependencies (only `math` + `src.config.actions`)
  - No pymem / dearpygui / threading / file I/O
- **Review**: P4 Step 1 Review APPROVED — 0 blocking issues, 3 non-blocking recommendations
- **Constraint**: `ai_engine.py` untouched — original God Class still fully operational

P3.1–P3.5 are done. 182 tests, 100% pass, 60% overall coverage (100% on config + data pipeline modules). CI workflow operational on Windows + Linux.

### P3.1 — Testing Infrastructure

- **Status**: ✅ Complete
- **Deliverables**: `tests/__init__.py`, `tests/conftest.py` (6 shared fixtures), `pytest.ini`, `.coveragerc`, `.github/workflows/test.yml`
- **Validation**: 17 infrastructure tests in `tests/test_infrastructure.py`

### P3.2 — Config Module Tests

- **Status**: ✅ Complete
- **Deliverables**: `tests/test_actions.py` (20 tests), `tests/test_offsets.py` (14 tests), `tests/test_logging.py` (11 tests)
- **Coverage**: `src/config/actions.py` 100%, `src/config/offsets.py` 100%, `src/logging_config.py` 100%

### P3.3 — Core Logic Tests

- **Status**: ✅ Complete — P3.3A + P3.3B + P3.3C all done
- **Deliverables**:
  - `P3_3_REVIEW.md` — 8-area testability classification (A/B/C)
  - `P3_3_TEST_RESULTS.md` — full P3.3 results with per-test listing
  - `tests/test_math_logic.py` (27 tests) — distance, angle, top-k
  - `tests/test_phase_filter.py` (32 tests) — phase/posture filter, renormalization
  - `tests/test_nova.py` (26 tests) — Nova threshold FSM
- **8 pure helper functions extracted into `ai_engine.py`**:
  - `calc_distance_2d`, `calc_relative_angle`, `select_top_k` (P3.3A)
  - `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs` (P3.3B)
  - `_POSTURE_STAND_EXCLUDE`, `_POSTURE_PRONE_EXCLUDE` constants (P3.3B)
  - `evaluate_nova` (P3.3C)

### P3.4 — Integration Testing

- **Status**: ✅ Complete
- **Deliverables**:
  - `tests/test_data_upgrade.py` (11 tests) — phase/enrage backfill, column order, mixed files
  - `tests/test_data_cleaner.py` (19 tests) — ETL pipeline: mapping, FSM, filtering, corrupted CSV
  - `tests/test_train_lgbm.py` (5 tests) — mini dataset training, model output, rare class filter, error logging
- **Coverage**: `data_upgrade.py` 100%, `data_cleaner.py` 100%, `train_lgbm.py` 100%

### P3.5 — CI Finalization

- **Status**: ✅ Complete
- README badges updated (tests: 182 passed, coverage: 60%)
- CHANGELOG.md updated (v0.2.0 + v0.3.0 entries)
- progress.md + activeContext.md updated
- P3_CLOSURE_REPORT.md generated

## Current Test Metrics

| Total tests | **581** (27 test files) |
|--------|-------|
| Pass rate | 100% |
| Overall coverage | **94%** |
| `ai_engine.py` coverage | **43%** |
| `state_tracker.py` coverage | **100%** |
| `memory_reader.py` coverage | **100%** |
| `predictor.py` coverage | **99%** |
| `recorder.py` coverage | **100%** |
| `overlay.py` coverage | **100%** |
| Config modules coverage | 100% (3/3 modules) |
| Data pipeline coverage | 100% (3/3 modules) |
| CI workflow | `.github/workflows/test.yml` (Windows + Ubuntu, Python 3.11/3.12) |

## Test File Inventory

| File | Tests | Phase | Target |
|------|-------|-------|--------|
| `tests/test_infrastructure.py` | 17 | P3.1 | Fixtures, config, discovery, CI |
| `tests/test_actions.py` | 20 | P3.2 | ACTION_DB, ACTION_MAPPING, phase/posture sets |
| `tests/test_offsets.py` | 14 | P3.2 | GameOffsets dataclass, field values, immutability |
| `tests/test_logging.py` | 11 | P3.2 | setup_logging, FileHandler, log output |
| `tests/test_math_logic.py` | 27 | P3.3A | calc_distance_2d, calc_relative_angle, select_top_k |
| `tests/test_phase_filter.py` | 32 | P3.3B | filter_probs_by_phase, filter_probs_by_posture, renormalize_probs |
| `tests/test_nova.py` | 26 | P3.3C | evaluate_nova |
| `tests/test_data_upgrade.py` | 11 | P3.4 | phase/enrage backfill, column order, mixed files |
| `tests/test_data_cleaner.py` | 19 | P3.4 | ETL: mapping, posture FSM, filtering, corrupted CSV |
| `tests/test_train_lgbm.py` | 5 | P3.4 | mini dataset training, model output, rare class filter |
| `tests/test_state_tracker.py` | 50 | P4.1 | CombatStateTracker: init, math, phase, enrage, posture FSM, nova, zone reset |
| `tests/test_memory_reader.py` | 27 | P4.2 | MemoryReader: pointer chains, zone, monster, player, HP, action, enrage |
| `tests/test_predictor.py` | 31 | P4.3 | ActionPredictor: model load, predict, feature format, filters, top-k, edge cases |

| `tests/test_recorder.py` | 34 | P4.4 | CombatRecorder: header, gating, recording, buffer, lifecycle, structural |

| `tests/test_overlay.py` | 41 | P4.5 | OverlayUI: zone gating, state updates, nova, prediction, throttle, display, DPG lifecycle |
| `tests/test_training_pipeline.py` | 11 | P5.4 | Pipeline flag: call order, frozen/dev cmd, clean/train failure, unknown action graceful |

## What Is Allowed Right Now

- Extracting new modules from `ai_engine.py` into `src/core/`, `src/data/`, `src/model/`, `src/ui/`
- Adding tests for extracted modules
- Updating `ai_engine.py` call sites to use extracted modules (keeping backward compat)
- CI configuration adjustments
- Documentation updates

## Hard Constraints (P4 Active)

1. **Project must remain runnable** — `python ai_engine.py` must still function after every extraction step
2. **No behavior changes** — all existing logic must produce identical outputs
3. **No model changes** — training and inference pipelines untouched
4. **No gameplay changes** — action mappings, posture rules, phase thresholds remain unchanged
## Success Criteria for P4

- [x] P4.1: StateTracker extracted — `src/core/state_tracker.py`, 50 tests, 100% coverage
- [x] P4.2: MemoryReader extracted — `src/core/memory_reader.py`, 27 tests, 100% coverage
- [x] P4.3: Predictor extracted — `src/model/predictor.py`, 31 tests, 99% coverage
- [x] P4.4: Recorder extracted — `src/data/recorder.py`, 34 tests, 100% coverage
- [x] P4.5: OverlayUI extracted — `src/ui/overlay.py`, 41 tests, 100% coverage
- [ ] P4.6: Main assembly — `main.py` + `ai_engine.py` backward compat stub
- [ ] Overall coverage ≥80%
- [ ] Git tag: `v0.4.0-architecture-refactor`
### Next Objective: P4 Step 6 Integration

Wire `ai_engine.py main()` to use the 5 extracted modules:
- Create `MemoryReader(pm, base)` → shared instance
- Create `CombatStateTracker()` → shared instance
- Create `ActionPredictor("models/fatalis_ai_model.pkl")`
- Create `CombatRecorder(memory_reader, state_tracker, buffer, lock)` → daemon thread
- Create `OverlayUI(memory_reader, state_tracker, predictor, buffer, lock)` → `run()`
- Remove duplicate logic from `ai_engine.py` (module-level functions, global state)
- Keep `python ai_engine.py` runnable as backward compat stub

Sequential extraction:
1. ✅ StateTracker → `src/core/state_tracker.py`
2. ✅ MemoryReader → `src/core/memory_reader.py`
3. ✅ ActionPredictor → `src/model/predictor.py`
4. ✅ CombatRecorder → `src/data/recorder.py`
5. ✅ OverlayUI → `src/ui/overlay.py`
6. 🔜 Main assembly → `main.py`
## Current Blockers

None. P4 Step 6 (Integration) is ready to begin.

### Current Development State

| Component | Status | Notes |
|-----------|:------|------|
| **Dashboard UI** | ✅ Complete | DPG control panel: tabs for console/training/log/settings. Game-less startup (pauses until pymem detects). StatusBar, LogView, TrainingPanel, button enable/disable. |
| **Bootstrap** | ✅ Complete | `DependencyChecker` — Python version + pip dep check + auto-install (before DPG starts). |
| **GameService** | ✅ Complete | Background daemon thread — polls for MonsterHunterWorld.exe every 2s. `attach_game()` creates P4 modules when found. 3-failure threshold for detach. |
| **Overlay Integration** | ❌ Deferred | Three approaches failed due to DPG 2.x / GLFW main-thread requirement. See "Failed Experiments" below. |
| **CJK Font** | ✅ Complete | Shared `src/ui/fonts.py` — Dashboard and Overlay both use `setup_cjk_font()` (msyh.ttc on Windows, fallback on others). |

#### Entry Points

| Command | Function |
|---------|----------|
| `python launch.py` | P5 Dashboard control center (recommended) |
| `python launch.py --pipeline` | P5.4 One-click data clean + model train |
| `python main.py` | P4 standalone transparent overlay (legacy) |
| `python ai_engine.py` | Legacy God Class (reference only) |

#### Architecture Snapshot

```
src/
├── core/          ← P4 (state_tracker, memory_reader)
├── model/         ← P4 (predictor)
├── data/          ← P4 (recorder)
├── ui/
│   ├── overlay.py ← P4.5 (standalone overlay — UNCHANGED from P4.5)
│   └── fonts.py   ← P5.1 (shared CJK font)
├── app/           ← P5 (controller, game_service, config)
├── bootstrap/     ← P5.1 (dependency checker)
├── dashboard/     ← P5 (main_window, log_view, training_panel, status_bar)
└── config/        ← P2 (actions, offsets — single source of truth)
```

### Failed Experiments

#### P5.2: OverlayService Integration (commit `6952114`)

**Goal**: Dashboard and transparent overlay coexist in one process.

**Attempted Approaches**:

| # | Method | Failure Reason |
|---|--------|---------------|
| A | Single DPG context + `create_viewport()` for secondary viewport | DPG 2.x renders `dpg.window()` widgets **only on primary viewport**. Secondary viewport is blank. |
| B | Overlay daemon thread + own DPG context | GLFW requires `glfwCreateWindow()` on **main thread only**. Non-main thread → undefined behavior → crash. |
| C | OverlayService + cross-thread `queue.Queue` commands | Same GLFW violation as B. Command routing doesn't change where GLFW calls execute. |

**Root Cause**: `dearpygui==2.3` uses GLFW as the windowing backend. GLFW requires all windowing operations on the thread that initialized the library. DPG 2.x cannot run two windowed contexts simultaneously in one process.

**Decision**: Move to dual-process architecture. Full record: `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`.

### Next Steps

1. **Revert P5.2 experimental code** — Restore `src/ui/overlay.py` to P4.5 standalone design. Remove overlay lifecycle methods from `AppController`. Restore `Dashboard` to remove overlay toggle button.
2. **Create `overlay.py`** — Standalone script at project root. Wires MemoryReader + StateTracker + Predictor + Recorder + OverlayUI. Equivalent to `main.py` but tailored for dual-process use.
3. **Rewrite `launch.py`** — Dual-process launcher: `subprocess.Popen(["python", "overlay.py"])` + Dashboard.
4. **Test** — Ensure ≥510 tests pass; verify both processes run independently on real machine.
5. **Tag** — `v0.5.0-dashboard` (stable Dashboard baseline before overlay process integration).
## Recent Decisions

#### Recent Decisions

- **P5.2 Experiment** (commit `6952114`): Three overlay integration approaches attempted and documented.
  - Solution A (single DPG context, `create_viewport()` + `configure_viewport(show=)`): widgets render only on primary viewport
  - Solution B (overlay daemon thread, own DPG context): GLFW crash (non-main thread window creation)
  - Solution C (OverlayService + `queue.Queue`): same GLFW crash as B
  - **Decision**: Dual-process architecture — Dashboard and Overlay as separate Python processes
  - **ADR**: `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`
- P5 Dashboard: ✅ functional — game detection, recording toggle, training subprocess, log view, CJK font
- P5.1 Bootstrap + game-less startup: ✅ functional — dep checker, GameService, lazy P4 module attach
- 510 tests pass (MPLBACKEND=Agg), P4 core untouched
- `python launch.py` runs Dashboard (control panel); `python main.py` runs standalone overlay (legacy)

### P5.4 Training Pipeline Integration (v1.1.0)

- **Status**: ✅ Complete
- **Deliverables**:
  - `launch.py` `--pipeline` flag: one-click `data_cleaner` → `train_lgbm`
  - `controller.start_training()` uses `--pipeline` (frozen/Dev dual-mode)
  - `data_cleaner.py`: unknown action filtering (labels not in `ACTION_DB`)
  - `train_lgbm.py`: unknown label detection + `stratify=y` with small-dataset fallback + NaN/non-numeric warnings
  - `build/BlackDragon.spec`: `data_cleaner` hidden import
  - `tests/test_training_pipeline.py`: 11 pipeline integration tests
  - ADR-P5.4 documented (Option A — `--pipeline` flag)
- **Metrics**: 581 tests, 100% pass; frozen `BlackDragon.exe --pipeline` verified exit 0
- **Constraint**: P4 core (`src/core/`, `src/model/`, `src/data/recorder.py`) unchanged — zero diff
- **Known gap**: Action 117 (triggered original bug) filtered as unknown; needs `ACTION_DB` investigation
