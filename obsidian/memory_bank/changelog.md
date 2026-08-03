# Changelog — BlackDragon Memory Bank

> 记录每个阶段的完成事件，与根目录 `CHANGELOG.md`（版本发布记录）互补。

---

### 2026-08-03 — P4 Step 4 Complete

#### Phase
P4 Architecture Refactoring (架构重构)

#### Completed
- **P4.4: Recorder Extraction**
  - Created `src/data/__init__.py`
  - Created `src/data/recorder.py` — `CombatRecorder` class (216 lines)
  - Created `tests/test_recorder.py` — 34 tests, 100% pass
  - `recorder.py` achieves **100% branch coverage**
  - `ai_engine.py` / `state_tracker.py` / `memory_reader.py` left untouched — dual-track maintained

#### API
- `CombatRecorder(memory_reader, state_tracker, action_buffer, action_lock, data_dir="data")`
- Lifecycle: `start()` (daemon thread, idempotent) / `stop()` (explicit close) / `run()` (thread target, NEVER called directly)
- Gating: `_should_pause()` — `is_recording` off OR zone != Fatalis → 1s sleep
- Frame: `_record_frame()` — MemoryReader read → action_buffer append (with lock) → CSV row
- CSV format identical to original `data_logger_thread`: timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id

#### Design Decisions
- All memory reads via **MemoryReader** (no direct pymem / pm.read_*)
- All state reads via **CombatStateTracker** (no shared_state dict) — `is_recording` / `phase` / `posture` / `is_enraged`
- Action ID appended to shared `action_buffer` under `action_lock` (Recorder is producer, UI is consumer)
- D3: single-frame exception → `logger.warning` → sleep → continue (daemon stays alive); `stop()` is the only exit
- CSV file created lazily on first successful frame (nested data_dir auto-created)
- Column list single source of truth: `CombatRecorder._COLUMNS` (test imports it to avoid drift)

#### Review
- P4 Step 4 Review: **APPROVED** (SF-1: `_should_pause()` try/except coverage parity with legacy — fixed)
- SF-1 fix: `run()` try boundary moved up 3 lines to cover `_should_pause()` → defensive parity with original `data_logger_thread` exception scope

#### Metrics
Tests: 290 → **324** (+34)
recorder.py coverage: **100%**
4 of 6 modules extracted (StateTracker + MemoryReader + Predictor + Recorder)

#### Known Environment Issue (pre-existing, NOT a regression)
- This machine's Tcl/Tk install is broken (`init.tcl` missing), so matplotlib intermittently
  falls back to TkAgg backend → flaky `test_train_lgbm.py` failure on plain `pytest`
- Reproduced WITHOUT P4.4 changes (deselecting new recorder tests still fails)
- Workaround: `MPLBACKEND=Agg pytest` → full suite green (324/324)
## 2026-08-02 — P4 Step 3 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.3: Predictor Extraction**
  - Created `src/model/__init__.py`
  - Created `src/model/predictor.py` — `ActionPredictor` class (201 lines)
  - Created `tests/test_predictor.py` — 31 tests, 100% pass
  - `predictor.py` achieves **99% branch coverage** (1 missed: defensive `if col in columns`)
  - `ai_engine.py` left untouched — backward compat maintained

### API
- `ActionPredictor(model_path)` → `predict(6 features)` → `[(class_id, prob), ...]`
- 4 static methods migrated from P3.3: `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs`, `select_top_k`
- 2 constants: `_POSTURE_STAND_EXCLUDE` (15 IDs), `_POSTURE_PRONE_EXCLUDE` (37 IDs)

### Design Decisions
- Dependencies: `joblib` + `pandas` + `numpy` + lazy `src.config.actions`
- No pymem / dearpygui / threading / StateTracker / MemoryReader
- Model load failure → `_model = None` → `predict()` returns `[]`
- Returns raw (class_id, prob) tuples — ACTION_DB display stays in caller (UI)
- Feature construction (6 columns, 4 categorical) 1:1 matching original `update_logic`

### Review
- P4 Step 3 Review: **APPROVED** (0 blocking, 2 non-blocking suggestions)

### Metrics
- Total tests: 259 → **290** (+31)
- Overall coverage: 68% → **72%**
- 3 of 6 modules extracted (StateTracker + MemoryReader + Predictor)

---

## 2026-08-02 — P4 Step 2 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.2: MemoryReader Extraction**
  - Created `src/core/memory_reader.py` — `MemoryReader` class (183 lines)
  - Created `tests/test_memory_reader.py` — 27 tests, 100% pass (mock pymem)
  - `memory_reader.py` achieves **100% branch coverage**
  - `ai_engine.py` left untouched — backward compat maintained

### Design Decisions
- Encapsulates all pymem process memory reads (9 public methods)
- Single dependency: `pymem` + `src.config.offsets`
- Zero business logic — returns raw data, no phase/enrage/posture/nova decisions
- Stateless beyond constructor (no cache, no mutable internal state) → thread-safe for multi-threaded use
- `check_zone` returns raw zone_id (no Fatalis=417 check) — business logic stays in caller
- `read_enrage_state` returns (0.0, 0.0) on failure → original fallback behavior preserved
- Not yet wired into ai_engine.py — dual-track status maintained

### Review
- P4 Step 2 Review: **APPROVED** (0 blocking, 3 non-blocking recommendations)

### Metrics
- Total tests: 232 → **259** (+27)
- Overall coverage: 64% → **68%**

---

## 2026-08-02 — P4 Step 1 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.1: StateTracker Extraction**
  - Created `src/core/__init__.py`
  - Created `src/core/state_tracker.py` — `CombatStateTracker` class (156 lines)
  - Created `tests/test_state_tracker.py` — 50 tests, 100% pass
  - `state_tracker.py` achieves **100% branch coverage**
  - `ai_engine.py` left untouched — backward compat maintained

### Design Decisions
- StateTracker encapsulates all shared_state dict semantics (7 state fields + 8 methods)
- Zero external dependencies: only `math` + `src.config.actions`
- `shared_state['action_id']` confirmed dead code — dropped
- `action_buffer` + `lock` deferred to P4 Step 4 (Recorder thread coordination)
- Not yet wired into ai_engine.py — standalone module for now

### Review
- P4 Step 1 Review: **APPROVED** (0 blocking, 3 non-blocking recommendations)

### Metrics
- Total tests: 182 → **232** (+50)
- Overall coverage: 60% → **64%**

---

## 2026-08-02 — P3 Complete

### Phase
P3 Test Safety Net (测试体系)

### Completed
- P3.1–P3.5: 182 tests, 60% coverage, GitHub Actions CI
- Tag: `v0.3.0-test-safety-net`

---

## 2026-06-25 — P2 Complete

### Phase
P2 Critical Fixes (P0 修复)

### Completed
- Logging, unified constants, posture FSM, bare except sweep
- Tag: `v0.2.0-p0-fixes`

---

## 2026-06-22 — P1 Complete

### Phase
P1 Project Standardization (项目优化)

### Completed
- README, .gitignore, requirements.txt, directory structure
- Tag: `v0.1.0-project-init`
