# Progress — BlackDragon

> Status source: `Refactoring_roadmap.md`

## Phase Overview

| Phase  | Name                           | Status         | Key Deliverables                                                                    | Tag    |
| ------ | ------------------------------ | -------------- | ----------------------------------------------------------------------------------- | ------ |
| **P1** | 项目优化 (Project Standardization) | **Complete**   | README, .gitignore, requirements.txt, directory structure                           | v0.1.0 |
| **P2** | P0 修复 (Critical Fixes)         | **Complete**   | Logging, unified actions.py, centralized offsets.py, posture FSM, bare except sweep | v0.2.0 |
| P3     | 测试体系 (Test Safety Net)         | **Complete**   | 182 tests (60% coverage), GitHub Actions CI                                         | v0.3.0 |
| P4     | 架构重构 (Architecture Refactor)   | **Complete**   | src/core/, src/data/, src/model/, src/ui/, main.py                                  | —      |
| P5     | 控制中心 (Dashboard + Overlay)     | **In Progress** | Dashboard UI (done), Bootstrap (done), Overlay integration (deferred)               | —      |
| P6     | 模型工程化 (Model Engineering)     | Planned        | Model versioning, incremental learning, docs, GitHub Release                        | —      |

## P1 — Project Standardization (Active)

**Goal**: Establish project infrastructure without modifying any core logic.

### Tasks
- [ ] Create `README.md` — project intro, install guide, usage, directory structure
- [ ] Create `.gitignore` — exclude .venv/, __pycache__/, *.csv, *.pkl, .idea/
- [ ] Create `requirements.txt` — pin all dependencies
- [ ] Create `CHANGELOG.md` — version history
- [ ] Create `archive/` directory — move mod.py there
- [ ] Create `data/` directory — move CSVs there
- [ ] Create `models/` directory — move .pkl and .png there
- [ ] Create `docs/` directory — move reference docs there
- [ ] Update file paths in all Python scripts to reflect new directory structure
- [ ] Create `tests/manual_checklist.md` — manual verification checklist
- [ ] Verify `python data_cleaner.py && python train_lgbm.py` still works
- [ ] Verify `python ai_engine.py` starts (game not required for import check)

### Constraints
- No changes to core Python logic
- No changes to game mechanics logic
- No changes to model behavior
- No changes to feature engineering
- No architecture refactoring

## P2 — Critical Fixes (Complete ✅)

See `Tech_debt.md` items #1, #2, #3. Extended with audit findings P2.4–P2.6.

- [x] Replace all `except: pass` with structured logging (#3) → `ea143d5`
- [x] Unify ACTION_MAPPING into single source of truth (#2) → `43bfcff`
- [x] Centralize memory offsets into config (#1) → `cb4d218`
- [x] Unify posture FSM transition sets (P2.4) → uncommitted
- [x] Fix `train_lgbm.py` bare except (P2.5) → uncommitted
- [x] Fix `enrage.py` bare except (P2.6) → uncommitted

**Closure report**: `docs/P2_CLOSURE_REPORT.md`

## P3 — Test Safety Net (Complete ✅)

**Completion date**: 2026-08-02

- [x] P3.1: Testing Infrastructure — pytest.ini, .coveragerc, CI workflow, conftest.py, 17 infrastructure tests
- [x] P3.2: Config Module Tests — test_actions (20), test_offsets (14), test_logging (11) → config 100%
- [x] P3.3: Core Logic Tests — 8 pure functions extracted, test_math_logic (27), test_phase_filter (32), test_nova (26)
- [x] P3.4: Integration Tests — test_data_upgrade (11), test_data_cleaner (19), test_train_lgbm (5)
- [x] P3.5: CI Finalization — README badges, changelog, closure report
- [x] Coverage: 60% overall, ai_engine.py 43%, config modules 100%, data pipeline modules 100%
- [x] All 182 tests pass, CI compatible with Windows + Linux, Python 3.11/3.12

**Closure report**: `P3_CLOSURE_REPORT.md`

## P4 — Architecture Refactor (Active 🔵)

**P4 Step 1–6 complete (2026-08-03). P4 Architecture Refactor COMPLETE ✅**

Sequential extraction from `ai_engine.py`:
- [x] **P4.1: StateTracker** → `src/core/state_tracker.py` — CombatStateTracker class, 50 tests, 100% coverage
- [x] **P4.2: MemoryReader** → `src/core/memory_reader.py` — 9 public methods, 27 tests, 100% coverage
- [x] **P4.3: ActionPredictor** → `src/model/predictor.py` — model load + inference pipeline, 31 tests, 99% coverage
- [x] **P4.4: CombatRecorder** → `src/data/recorder.py` — daemon recording thread, 34 tests, 100% coverage
- [x] **P4.5: OverlayUI** → `src/ui/overlay.py` — DearPyGui overlay UI, 41 tests, 100% coverage
- [x] **P4.6: Main assembly** → `main.py` — composition root (85 lines), 20 tests, 100% coverage

## P5 — Model Engineering (Planned)

- [ ] Model version management with metadata
- [ ] Incremental training via LightGBM `init_model`
- [ ] Data schema versioning for CSVs
- [ ] Complete documentation (installation, usage, model training, memory RE guide)
- [ ] CI/CD: lint + test + release workflows
- [ ] GitHub Release v1.0.0

---

### P5 — Control Center (In Progress)

**P5 Dashboard ✅, P5.1 Bootstrap ✅, P5.2 Overlay Integration Deferred**

#### P5 — Dashboard
- [x] **AppController** → `src/app/controller.py` — lifecycle coordinator
- [x] **AppConfig** → `src/app/config.py` — JSON settings persistence
- [x] **Dashboard UI** → `src/dashboard/main_window.py` — control panel (tabs, StatusBar, LogView, TrainingPanel)
- [x] **StatusBar** → `src/dashboard/status_bar.py` — game/model/record/overlay indicators
- [x] **LogView** → `src/dashboard/log_view.py` — real-time log display (QueueHandler)
- [x] **TrainingPanel** → `src/dashboard/training_panel.py` — subprocess training UI
- [x] **launch.py** → composition root (bootstrap + GameService + Dashboard)
- [x] CJK font → `src/ui/fonts.py` — shared msyh.ttc loading
- [x] Bug fixes: window no_resize/no_move, font garbled, bootstrap import

#### P5.1 — Bootstrap + Game-less Mode
- [x] **DependencyChecker** → `src/bootstrap/checker.py` — Python version + pip deps
- [x] **GameService** → `src/app/game_service.py` — background detection + attach/detach
- [x] **Game-less startup** — Dashboard runs without game; auto-attach on detection
- [x] **launch.py no module-level pymem** — bootstrap runs before pymem import

#### P5.2 — Overlay Integration (EXPERIMENTAL — Deferred)
- [x] **Attempted: OverlayService thread model** — failed (GLFW main-thread restriction)
- [x] **Attempted: Single-context multi-viewport** — failed (widgets render only on primary viewport)
- [x] **Attempted: Command queue + thread** — failed (same GLFW violation)
- [x] **ADR-P5.2** → `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`
- [ ] **Dual-process architecture** (future): `overlay.py` standalone + `launch.py` subprocess launcher
## Current State Summary

- **Phase**: P5 (Control Center) — Dashboard ✅, P5.1 Bootstrap ✅, P5.2 Overlay Integration deferred
- **Project runs**: Yes — `python launch.py` (P5 Dashboard) or `python main.py` (P4 overlay)
- **Tests**: **510** (20 test files, 100% pass rate)
- **Coverage**: **72%** overall; Dashboard components 85-98%; P4 core 100%
- **P5 New modules**:
  - `src/app/controller.py` — AppController (332 lines, lifecycle + status + training)
  - `src/app/config.py` — AppConfig (87 lines, JSON persistence)
  - `src/app/game_service.py` — GameService (95 lines, bg game detection)
  - `src/bootstrap/checker.py` — DependencyChecker (173 lines, env check + pip)
  - `src/dashboard/main_window.py` — Dashboard (167 lines, DPG tabs + status)
  - `src/dashboard/status_bar.py` — StatusBar (56 lines)
  - `src/dashboard/log_view.py` — LogView (60 lines)
  - `src/dashboard/training_panel.py` — TrainingPanel (62 lines)
  - `src/ui/fonts.py` — Shared CJK font (62 lines)
  - `launch.py` — P5 composition root (61 lines)
- **P4 core status**: `src/core/`, `src/model/`, `src/data/` — zero modifications since P4.6
- **P5.2 experiment** (commit `6952114`): OverlayService thread model saved as historical reference
- **Next**: Revert P5.2 experimental overlay code → implement dual-process architecture
- **CI/CD**: GitHub Actions (pytest + coverage on Windows/Ubuntu, Python 3.11/3.12)
- **ADR**: `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`
