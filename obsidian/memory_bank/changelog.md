# Changelog — BlackDragon Memory Bank

> 记录每个阶段的完成事件，与根目录 `CHANGELOG.md`（版本发布记录）互补。

---

### 2026-08-04 — PyInstaller Frozen Support + v1.0 Release Candidate

#### Phase
P5 Control Center (控制中心) — PyInstaller + RC ✅

#### Completed
- **PyInstaller 打包支持** — 双 EXE (`BlackDragon.exe` + `BlackDragonOverlay.exe`) 通过 `--onedir` COLLECT 构建
  - `build/BlackDragon.spec` + `build/BlackDragonOverlay.spec` — hidden imports (dearpygui, lightgbm, sklearn, pymem, src/*)
  - `scripts/build_exe.ps1` — 一键构建 (test → clean → build → merge → surface data/model)
  - Surfacing: `_internal/models/` → `dist/BlackDragon/models/` (bundled model); `_internal/data/` → `dist/BlackDragon/data/` (training dataset)
  - Frozen 路径修复: `controller.data_dir` frozen-aware; `start_training` cwd 固定到 exe 目录; `start_overlay` sibling exe spawn
  - UTF-8 编码修复: `--train` 冻 冻结启动 `sys.stdout.reconfigure(encoding="utf-8")`
  - `os.makedirs("models", exist_ok=True)` 在 `train_lgbm.py` 中确保模型输出目录存在

- **Runtime Bug Fixes**: CSV 路径 (bug #1), Training subprocess 复用 Dashboard (bug #2), Training data 缺失 #3), Model 首 首次加载 (bug #4)
- **RC Runtime Test**: 6/6 场景通过 (clean install / dashboard / overlay / data / model / training)
- **READY 更新**: LICENSE (MIT), CONTRIBUTING.md, SECURITY.md; README badges → 551 tests / 94%
- **KB v1.0**: 50 active docs + 16 legacy archived; 13 audit/build docs
- **ADR**: ADR-P5.3 status 更新为 Decided

#### Metrics
- Tests: 541 → **551** (+10 net: 7 frozen-path + dashboard UI)
- Coverage: 94% (unchanged)
- `dist/BlackDragon/` package: 227 MB (two EXEs + surfaced models/data)

#### Review
- RC tests all passed; release candidate ready

### 2026-08-04 — P5.3 Auto-Start + Recording Default (ADR-P5.3)

#### Phase
P5 Control Center (控制中心) — Auto-Start ✅

#### Completed
- **ADR-P5.3 方案 A 实施**（`obsidian/docs/architecture/ADR-P5.3-auto-start.md`）
  - `src/app/config.py`: `auto_start_overlay` 默认值 `False` → **`True`**；新增 `auto_record: bool = True`
  - `launch.py`: 启动覆盖层子进程改为 **`if config.auto_start_overlay: controller.start_overlay()`**（默认自动启动）
  - `overlay.py`: 读取共享 `AppConfig` 决定录制默认状态（`CombatStateTracker(is_recording=config.auto_record)`）；新增游戏连接**重试循环**（`_RETRY_INTERVAL=2.0`，`_MAX_RETRIES=60`）——Dashboard 启动可先于游戏，overlay 在游戏出现后自动进入工作状态
  - `src/app/controller.py`: `attach_game` 使用 `self._config.auto_record` 初始化录制状态
  - Dashboard 手动控制（start/stop overlay、toggle recording）**保持不变**

#### API
- `python launch.py` — 默认自动启动 Overlay 子进程 + Dashboard
- 配置项: `auto_start_overlay=True`（默认）、`auto_record=True`（默认），可通过 `blackdragon_config.json` 关闭

#### Design Decisions
- 双进程架构保持（P5.3 / ADR-P5.2）——overlay 仍是独立子进程，不恢复线程 Overlay
- overlay 重试循环使 launch 的"先启 overlay 后开游戏"场景无缝衔接
- 配置默认值遵循需求（auto-start + auto-record 均默认开启）；用户可显式关闭
- P4 core（`src/core/`、`src/model/`、`src/data/`、`main.py`）— **零 diff**

#### Metrics
- Tests: 532 → **541**（+9 net：新增 10，重命名 1）
- Coverage: 总体 **94%**（此前 93%）；`overlay.py` 100%；`launch.py` 36%→**86%**
- 新增测试：launch auto_start gating（3）、overlay retry（2）+ auto_record flow（2）、config defaults（2）、controller attach auto_record（2）

#### Review
- 待 reviewer 审查

### 2026-08-04 — P5.3 Dual-Process Architecture Complete

#### Phase
P5 Control Center (控制中心) — Dual-Process Overlay ✅

#### Completed
- **P5.3: Dashboard + Overlay 双进程架构** (per ADR-P5.2)
  - Reverted `src/ui/overlay.py` to P4.5 standalone design (removed P5.2 thread/queue/start/stop/show/hide command API) — `run()` is now the only lifecycle entry, blocking in the process's own main thread
  - Cleaned `AppController`: removed OverlayUI in-process lifecycle from attach_game/detach_game/shutdown; added **subprocess-based** overlay management (`start_overlay`/`stop_overlay`/`is_overlay_running`) — Dashboard launches `python overlay.py`
  - Added `overlay_script` config field (AppConfig, default `overlay.py`)
  - Created `overlay.py` — standalone overlay process entry (composition root, equivalent to main.py)
  - Rewrote `launch.py` — dual-process launcher: `controller.start_overlay()` (spawns overlay.py subprocess) + Dashboard
  - Dashboard UX: "启动覆盖层" button now launches/terminates the overlay **subprocess** (no more in-process toggle); StatusBar shows overlay process status (运行中/未启动)

#### API
- `python launch.py` — 双进程: Overlay 子进程 + Dashboard 控制中心（推荐）
- `python overlay.py` — 独立覆盖层进程
- `python main.py` — P4 standalone overlay (legacy)

#### Design Decisions
- GLFW main-thread 限制通过**进程级隔离**解决：每个进程有自己的 DPG context + 主线程
- `attach_game` 不再 import `src.ui.overlay`（dashboard 进程不创建 OverlayUI）
- `detach_game` 不终止覆盖层子进程（独立进程，用户手动关闭）
- Overlay 子进程 stdout/stderr 重定向到 DEVNULL（非交互进程）

#### Metrics
- Tests: 510 → **532** (+22 net: removed 8 P5.2 tests, added 30 P5.3 tests)
- `overlay.py` coverage: **100%**; `src/ui/overlay.py` coverage: **100%**; overall ~93%
- P4 core (`src/core/`, `src/model/`, `src/data/`) — **zero diff**
- `main.py` (P4.6) untouched

#### Review
- P5.3 implementation complete, all tests pass (MPLBACKEND=Agg)

### 2026-08-03 — P5.2 Overlay Integration Experiment (Deferred)

#### Phase
P5 Control Center (控制中心) — Experimental

#### Attempted
- **P5.2: Overlay Integration** — Three approaches tested to integrate transparent overlay with Dashboard
  - Solution A: Single DPG context + `create_viewport()` multi-viewport → widgets render only on primary viewport
  - Solution B: Overlay daemon thread + own DPG context → GLFW crash (non-main thread window creation)
  - Solution C: OverlayService + cross-thread `queue.Queue` commands → same GLFW violation
- Experiment saved as commit `6952114` (30 files, 510 tests)
- ADR written: `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`

#### Root Cause
`dearpygui==2.3` uses GLFW as windowing backend. GLFW requires all `glfwCreateWindow()` calls on the main thread. DPG 2.x cannot run two windowed contexts simultaneously in one process.

#### Decision
Dual-process architecture: Dashboard and Overlay as separate Python processes. Each has its own DPG context on its own main thread. Overlay integration deferred to next iteration.

#### Metrics
- Tests: 510 (all pass, P4 core unchanged)
- Mock tests pass; real DPG on Windows fails at overlay thread creation
### 2026-08-03 — P4 Step 6 Complete + v0.5.0 Cleanup

#### Phase
P4 Architecture Refactoring (架构重构) — Complete ✅

#### Completed
- **P4.6: Integration**
  - Created `main.py` — application composition root (~85 lines)
  - Created `tests/test_main_integration.py` — 20 tests, 100% pass
  - `ai_engine.py` left untouched — retained as legacy reference + P3 test-compat entry
  - `python main.py` = new recommended entry; `python ai_engine.py` = legacy fallback
  - 385 tests total, all pass (MPLBACKEND=Agg)

- **v0.5.0 Cleanup**
  - Moved `enrage.py` → `archive/` (research tool, no test deps)
  - Moved 8 P2/P3 closure reports → `archive/legacy_reports/`
  - Updated `README.md` (badges 385/72%, project structure tree, quick start, roadmap)
  - Updated `CHANGELOG.md` (v0.4.0 + v0.5.0 entries)
  - Updated `requirements.txt` (runtime vs test dep comments)
  - Fixed `test_main_integration.py` cross-platform import (stub pymem/dearpygui for Linux CI)

#### API
- `python main.py` — P4+ composition root (connects pymem → MemoryReader → StateTracker → Predictor → Recorder daemon → OverlayUI blocking)
- `python ai_engine.py` — legacy God Class (unchanged)

#### Design Decisions
- Zero-touch `ai_engine.py`: kept frozen for P3 test imports (85 tests) + fallback
- `main.py` is pure wiring — no business logic, no global mutable state (AST-verified)
- Shared instances (MemoryReader/StateTracker/buffer/lock) created once, injected by reference
- Linux CI cross-platform: stub modules pre-installed in sys.modules before `import main`

#### Metrics
- Tests: 365 → **385** (+20)
- `main.py` coverage: **100%**
- Overall coverage: **72%**
- P4 complete: all 6 steps done, 5 modules extracted, integration wired

#### Review
- P4.6 Review: **APPROVED** (0 blockers, 2 non-blocking suggestions)
### 2026-08-03 — P4 Step 5 Complete

#### Phase
P4 Architecture Refactoring (架构重构)

#### Completed
- **P4.5: OverlayUI Extraction**
  - Created `src/ui/__init__.py`
  - Created `src/ui/overlay.py` — `OverlayUI` class (289 lines)
  - Created `tests/test_overlay.py` — 41 tests, 100% pass
  - `overlay.py` achieves **100% branch coverage**
  - `ai_engine.py` / all 4 existing P4 modules left untouched — dual-track maintained

#### API
- `OverlayUI(memory_reader, state_tracker, predictor, action_buffer, action_lock)`
- `run()` — DPG event loop with try/finally for guaranteed destroy_context
- `_compute_frame()` — pure logic, 0 DPG calls, 1:1 order match with original update_logic
- `_apply_display()` — thin DPG layer (set_value / configure_item)
- `_setup_dpg()` — DPG context + font + window + viewport + Win32 ctypes transparent overlay
- `_compute_ai_display()` — nova warning / prediction throttle / ACTION_DB formatting
- `last_action` dropped — StateTracker owns posture FSM cursor

#### Design Decisions
- Constructor: only stores 5 injected deps — zero DPG/ctypes side effects → testable without real window
- `_compute_frame` structurally verified to contain no `dpg.` calls (regex test)
- Win32 ctypes isolated to `_apply_win32_overlay()` method body — `import src.ui.overlay` cross-platform safe
- AI prediction throttle (0.5s) kept in UI layer (`_last_ai_time`) — not a game logic concern
- DPG text/color updates separated from computation → `_compute_frame` returns dict, `_apply_display` applies
- CSV column display in state_text: no `posture` field (matching original)

#### Review
- P4 Step 5 Review: **APPROVED** — 0 blockers, 1 non-blocking observation (DPG configure_item order)

#### Metrics
- Tests: 324 → **365** (+41)
- overlay.py coverage: **100%**
- 5 of 6 modules extracted (StateTracker + MemoryReader + Predictor + Recorder + OverlayUI)
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
