# Active Context — BlackDragon

## Current Phase

**P4 Step 5 Complete → P4 Step 6 Pending (Integration)**

## Current Goal

Architecture refactoring in progress. Steps 1–5 (all modules) complete. Next: Step 6 — Main assembly: wire `ai_engine.py main()` to use extracted modules (MemoryReader + StateTracker + Predictor + CombatRecorder + OverlayUI), remove duplicate logic, keep backward compat.

## Dual-Track Status

| Track | Status | Description |
|-------|--------|-------------|
| **Legacy** | `ai_engine.py` (484 lines) | God Class still fully operational, zero modifications |
| **Extracted** | `src/core/state_tracker.py` | CombatStateTracker — pure state management, 50 tests ✅ |
| **Extracted** | `src/core/memory_reader.py` | MemoryReader — all pymem reads, 27 tests ✅ |
| **Extracted** | `src/model/predictor.py` | ActionPredictor — model load + inference, 31 tests ✅ |
| **Extracted** | `src/data/recorder.py` | CombatRecorder — daemon recording thread, 34 tests ✅ |
| **Extracted** | `src/ui/overlay.py` | OverlayUI — DearPyGui overlay, 41 tests ✅ |
| **Pending** | `main.py` | Step 6 — Integration wiring |

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

| Total tests | **365** (16 test files) |
|--------|-------|
| Pass rate | 100% |
| Overall coverage | **72%** |
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

## Recent Decisions

- **P4 Step 5 completed**: OverlayUI extracted — DearPyGui overlay, 41 tests, 100% coverage
- `_compute_frame` is pure logic: 0 DPG calls (structurally verified by regex), 1:1 order match with original update_logic
- `self.last_action` dropped — StateTracker owns posture FSM cursor internally
- `_apply_win32_overlay` isolated to method body — `import src.ui.overlay` cross-platform safe (no module-level ctypes)
- Constructor: only 5 injected deps stored (MemoryReader + StateTracker + Predictor + buffer + lock); zero DPG/ctypes
- `run()` uses try/finally for guaranteed `dpg.destroy_context()` — improvement over original
- P4.5 Review: APPROVED — 0 blockers, 1 non-blocking observation (DPG configure_item order, visually identical)
- Full suite: 365 tests pass (MPLBACKEND=Agg; pre-existing Tcl environment issue on this machine)
- All 5 modules extracted; 0 modifications to ai_engine.py
